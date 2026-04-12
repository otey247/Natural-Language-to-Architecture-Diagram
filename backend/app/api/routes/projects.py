"""Projects router – architecture diagram project management."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    ComponentItem,
    ComponentItemPublic,
    DiagramEdge,
    DiagramEdgeCreate,
    DiagramEdgePublic,
    DiagramEdgeUpdate,
    DiagramJsonUpdate,
    DiagramNode,
    DiagramNodeCreate,
    DiagramNodePublic,
    DiagramNodeUpdate,
    DiagramVersion,
    DiagramVersionPublic,
    DiagramVersionsPublic,
    GenerationRequest,
    GenerationResult,
    Message,
    Project,
    ProjectCreate,
    ProjectPublic,
    ProjectsPublic,
    ProjectUpdate,
    PromptRevision,
    PromptRevisionPublic,
)
from app.services.generation import (
    GeneratedDiagram,
    generate_architecture,
    refine_architecture,
)

router = APIRouter(prefix="/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_project_or_404(session: SessionDep, project_id: uuid.UUID) -> Project:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _require_owner(project: Project, current_user: Any) -> None:
    if not current_user.is_superuser and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")


def _latest_version(
    session: SessionDep, project_id: uuid.UUID
) -> DiagramVersion | None:
    stmt = (
        select(DiagramVersion)
        .where(DiagramVersion.project_id == project_id)
        .order_by(col(DiagramVersion.version_number).desc())
    )
    return session.exec(stmt).first()


def _next_version_number(session: SessionDep, project_id: uuid.UUID) -> int:
    stmt = select(func.max(DiagramVersion.version_number)).where(
        DiagramVersion.project_id == project_id
    )
    result = session.exec(stmt).one()
    return (result or 0) + 1


def _persist_generation(
    session: SessionDep,
    project: Project,
    diagram: GeneratedDiagram,
    current_user_id: uuid.UUID,
) -> tuple[DiagramVersion, list[DiagramNode], list[DiagramEdge], list[ComponentItem]]:
    """Persist a GeneratedDiagram to the database and return DB objects."""
    dv = DiagramVersion(
        project_id=project.id,
        version_number=diagram.version_number,
        notes_markdown=diagram.notes_markdown,
        created_by=current_user_id,
    )
    session.add(dv)
    session.flush()  # get dv.id

    db_nodes: list[DiagramNode] = []
    node_id_map: dict[uuid.UUID, uuid.UUID] = {}
    for raw in diagram.nodes:
        node = DiagramNode(
            diagram_version_id=dv.id,
            label=raw.label,
            node_type=raw.node_type,
            provider=raw.provider,
            x_position=raw.x,
            y_position=raw.y,
            metadata_json=json.dumps(raw.metadata) if raw.metadata else None,
        )
        session.add(node)
        session.flush()
        node_id_map[raw.id] = node.id
        db_nodes.append(node)

    db_edges: list[DiagramEdge] = []
    for raw_e in diagram.edges:
        src = node_id_map.get(raw_e.source_id)
        tgt = node_id_map.get(raw_e.target_id)
        if src and tgt:
            edge = DiagramEdge(
                diagram_version_id=dv.id,
                source_node_id=src,
                target_node_id=tgt,
                label=raw_e.label,
            )
            session.add(edge)
            db_edges.append(edge)

    db_components: list[ComponentItem] = []
    for raw_c in diagram.components:
        comp = ComponentItem(
            diagram_version_id=dv.id,
            name=raw_c.name,
            component_type=raw_c.component_type,
            provider=raw_c.provider,
            description=raw_c.description,
            role_summary=raw_c.role_summary,
        )
        session.add(comp)
        db_components.append(comp)

    session.commit()
    session.refresh(dv)
    return dv, db_nodes, db_edges, db_components


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------


@router.get("/", response_model=ProjectsPublic)
def list_projects(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """List all projects owned by the current user."""
    projects, count = crud.get_projects(
        session=session, owner_id=current_user.id, skip=skip, limit=limit
    )
    return ProjectsPublic(
        data=[ProjectPublic.model_validate(p) for p in projects], count=count
    )


@router.post("/", response_model=ProjectPublic)
def create_project(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    project_in: ProjectCreate,
) -> Any:
    """Create a new project."""
    project = crud.create_project(
        session=session, project_in=project_in, owner_id=current_user.id
    )
    return project


@router.get("/{project_id}", response_model=ProjectPublic)
def read_project(
    session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID
) -> Any:
    """Get a single project."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)
    return project


@router.patch("/{project_id}", response_model=ProjectPublic)
def update_project(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    project_id: uuid.UUID,
    project_in: ProjectUpdate,
) -> Any:
    """Update a project's metadata."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)
    return crud.update_project(
        session=session, db_project=project, project_in=project_in
    )


@router.delete("/{project_id}", response_model=Message)
def delete_project(
    session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID
) -> Message:
    """Delete a project and all its data."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)
    crud.delete_project(session=session, db_project=project)
    return Message(message="Project deleted successfully")


@router.post("/{project_id}/duplicate", response_model=ProjectPublic)
def duplicate_project(
    session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID
) -> Any:
    """Duplicate a project (metadata + latest diagram version)."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)

    new_project = Project(
        title=f"{project.title} (copy)",
        description=project.description,
        current_prompt=project.current_prompt,
        cloud_context=project.cloud_context,
        diagram_type=project.diagram_type,
        owner_id=current_user.id,
    )
    session.add(new_project)
    session.flush()

    latest = _latest_version(session, project_id)
    if latest:
        new_dv = DiagramVersion(
            project_id=new_project.id,
            version_number=1,
            diagram_json=latest.diagram_json,
            layout_json=latest.layout_json,
            notes_markdown=latest.notes_markdown,
            created_by=current_user.id,
        )
        session.add(new_dv)
        session.flush()

        # copy nodes
        orig_nodes = session.exec(
            select(DiagramNode).where(DiagramNode.diagram_version_id == latest.id)
        ).all()
        node_id_map: dict[uuid.UUID, uuid.UUID] = {}
        for n in orig_nodes:
            new_n = DiagramNode(
                diagram_version_id=new_dv.id,
                label=n.label,
                node_type=n.node_type,
                provider=n.provider,
                metadata_json=n.metadata_json,
                x_position=n.x_position,
                y_position=n.y_position,
            )
            session.add(new_n)
            session.flush()
            node_id_map[n.id] = new_n.id

        # copy edges
        orig_edges = session.exec(
            select(DiagramEdge).where(DiagramEdge.diagram_version_id == latest.id)
        ).all()
        for e in orig_edges:
            new_src = node_id_map.get(e.source_node_id)
            new_tgt = node_id_map.get(e.target_node_id)
            if new_src and new_tgt:
                session.add(
                    DiagramEdge(
                        diagram_version_id=new_dv.id,
                        source_node_id=new_src,
                        target_node_id=new_tgt,
                        label=e.label,
                        metadata_json=e.metadata_json,
                    )
                )

        # copy components
        orig_comps = session.exec(
            select(ComponentItem).where(ComponentItem.diagram_version_id == latest.id)
        ).all()
        for c in orig_comps:
            session.add(
                ComponentItem(
                    diagram_version_id=new_dv.id,
                    name=c.name,
                    component_type=c.component_type,
                    provider=c.provider,
                    description=c.description,
                    role_summary=c.role_summary,
                )
            )

    session.commit()
    session.refresh(new_project)
    return new_project


# ---------------------------------------------------------------------------
# Generation endpoints
# ---------------------------------------------------------------------------


@router.post("/{project_id}/generate", response_model=GenerationResult)
def generate_diagram(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    project_id: uuid.UUID,
    body: GenerationRequest,
) -> Any:
    """Generate an architecture diagram from a natural language prompt."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)

    version_number = _next_version_number(session, project_id)
    diagram = generate_architecture(
        prompt=body.prompt,
        cloud_context=body.cloud_context or project.cloud_context,
        diagram_type=body.diagram_type or project.diagram_type,
        version_number=version_number,
    )

    # Save prompt revision
    revision = PromptRevision(
        project_id=project.id,
        prompt_text=body.prompt,
        created_by=current_user.id,
    )
    session.add(revision)

    # Update project metadata
    project.current_prompt = body.prompt
    if body.cloud_context:
        project.cloud_context = body.cloud_context
    if body.diagram_type:
        project.diagram_type = body.diagram_type
    project.updated_at = datetime.now(timezone.utc)
    session.add(project)

    dv, db_nodes, db_edges, db_components = _persist_generation(
        session, project, diagram, current_user.id
    )

    return GenerationResult(
        diagram_version=DiagramVersionPublic.model_validate(dv),
        nodes=[DiagramNodePublic.model_validate(n) for n in db_nodes],
        edges=[DiagramEdgePublic.model_validate(e) for e in db_edges],
        components=[ComponentItemPublic.model_validate(c) for c in db_components],
        notes_markdown=dv.notes_markdown or "",
    )


@router.post("/{project_id}/refine", response_model=GenerationResult)
def refine_diagram(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    project_id: uuid.UUID,
    body: GenerationRequest,
) -> Any:
    """Refine an existing architecture with an additional prompt."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)

    base_prompt = project.current_prompt or ""
    version_number = _next_version_number(session, project_id)
    diagram = refine_architecture(
        existing_prompt=base_prompt,
        refinement_prompt=body.prompt,
        cloud_context=body.cloud_context or project.cloud_context,
        diagram_type=body.diagram_type or project.diagram_type,
        version_number=version_number,
    )

    revision = PromptRevision(
        project_id=project.id,
        prompt_text=body.prompt,
        created_by=current_user.id,
    )
    session.add(revision)

    project.current_prompt = f"{base_prompt} {body.prompt}".strip()
    project.updated_at = datetime.now(timezone.utc)
    session.add(project)

    dv, db_nodes, db_edges, db_components = _persist_generation(
        session, project, diagram, current_user.id
    )

    return GenerationResult(
        diagram_version=DiagramVersionPublic.model_validate(dv),
        nodes=[DiagramNodePublic.model_validate(n) for n in db_nodes],
        edges=[DiagramEdgePublic.model_validate(e) for e in db_edges],
        components=[ComponentItemPublic.model_validate(c) for c in db_components],
        notes_markdown=dv.notes_markdown or "",
    )


@router.post("/{project_id}/regenerate-notes", response_model=Message)
def regenerate_notes(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    project_id: uuid.UUID,
) -> Any:
    """Regenerate the notes for the latest diagram version."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)

    latest = _latest_version(session, project_id)
    if not latest:
        raise HTTPException(status_code=404, detail="No diagram version found")

    from app.services.generation import (
        detect_components,
        detect_provider,
        generate_notes,
    )

    combined = " ".join(
        filter(
            None, [project.current_prompt, project.cloud_context, project.diagram_type]
        )
    )
    provider = detect_provider(combined)
    specs = detect_components(combined)
    notes = generate_notes(provider, specs, project.current_prompt or "")

    latest.notes_markdown = notes
    session.add(latest)
    project.updated_at = datetime.now(timezone.utc)
    session.add(project)
    session.commit()

    return Message(message="Notes regenerated successfully")


@router.post(
    "/{project_id}/regenerate-components", response_model=list[ComponentItemPublic]
)
def regenerate_components(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    project_id: uuid.UUID,
) -> Any:
    """Regenerate the component inventory for the latest diagram version."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)

    latest = _latest_version(session, project_id)
    if not latest:
        raise HTTPException(status_code=404, detail="No diagram version found")

    from app.services.generation import detect_components, detect_provider

    combined = " ".join(
        filter(
            None, [project.current_prompt, project.cloud_context, project.diagram_type]
        )
    )
    provider = detect_provider(combined)
    specs = detect_components(combined)

    # Delete existing components for this version
    old_comps = session.exec(
        select(ComponentItem).where(ComponentItem.diagram_version_id == latest.id)
    ).all()
    for c in old_comps:
        session.delete(c)
    session.flush()

    new_comps: list[ComponentItem] = []
    for spec in specs:
        comp = ComponentItem(
            diagram_version_id=latest.id,
            name=spec.label,
            component_type=spec.node_type,
            provider=provider,
            description=spec.description,
            role_summary=spec.role_summary,
        )
        session.add(comp)
        new_comps.append(comp)

    project.updated_at = datetime.now(timezone.utc)
    session.add(project)
    session.commit()
    for c in new_comps:
        session.refresh(c)

    return [ComponentItemPublic.model_validate(c) for c in new_comps]


# ---------------------------------------------------------------------------
# Version management
# ---------------------------------------------------------------------------


@router.get("/{project_id}/versions", response_model=DiagramVersionsPublic)
def list_versions(
    session: SessionDep,
    current_user: CurrentUser,
    project_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
) -> Any:
    """List all diagram versions for a project."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)

    count_stmt = (
        select(func.count())
        .select_from(DiagramVersion)
        .where(DiagramVersion.project_id == project_id)
    )
    count = session.exec(count_stmt).one()
    stmt = (
        select(DiagramVersion)
        .where(DiagramVersion.project_id == project_id)
        .order_by(col(DiagramVersion.version_number).desc())
        .offset(skip)
        .limit(limit)
    )
    versions = session.exec(stmt).all()
    return DiagramVersionsPublic(
        data=[DiagramVersionPublic.model_validate(v) for v in versions], count=count
    )


@router.post(
    "/{project_id}/versions/{version_id}/restore", response_model=DiagramVersionPublic
)
def restore_version(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
) -> Any:
    """Restore a previous diagram version by creating a new version from it."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)

    source_dv = session.get(DiagramVersion, version_id)
    if not source_dv or source_dv.project_id != project_id:
        raise HTTPException(status_code=404, detail="Diagram version not found")

    new_version_number = _next_version_number(session, project_id)
    new_dv = DiagramVersion(
        project_id=project_id,
        version_number=new_version_number,
        diagram_json=source_dv.diagram_json,
        layout_json=source_dv.layout_json,
        notes_markdown=source_dv.notes_markdown,
        created_by=current_user.id,
    )
    session.add(new_dv)
    session.flush()

    # copy nodes
    orig_nodes = session.exec(
        select(DiagramNode).where(DiagramNode.diagram_version_id == source_dv.id)
    ).all()
    node_id_map: dict[uuid.UUID, uuid.UUID] = {}
    for n in orig_nodes:
        new_n = DiagramNode(
            diagram_version_id=new_dv.id,
            label=n.label,
            node_type=n.node_type,
            provider=n.provider,
            metadata_json=n.metadata_json,
            x_position=n.x_position,
            y_position=n.y_position,
        )
        session.add(new_n)
        session.flush()
        node_id_map[n.id] = new_n.id

    # copy edges
    orig_edges = session.exec(
        select(DiagramEdge).where(DiagramEdge.diagram_version_id == source_dv.id)
    ).all()
    for e in orig_edges:
        new_src = node_id_map.get(e.source_node_id)
        new_tgt = node_id_map.get(e.target_node_id)
        if new_src and new_tgt:
            session.add(
                DiagramEdge(
                    diagram_version_id=new_dv.id,
                    source_node_id=new_src,
                    target_node_id=new_tgt,
                    label=e.label,
                    metadata_json=e.metadata_json,
                )
            )

    project.updated_at = datetime.now(timezone.utc)
    session.add(project)
    session.commit()
    session.refresh(new_dv)
    return DiagramVersionPublic.model_validate(new_dv)


# ---------------------------------------------------------------------------
# Diagram JSON update
# ---------------------------------------------------------------------------


@router.patch("/{project_id}/diagram", response_model=DiagramVersionPublic)
def update_diagram_json(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    project_id: uuid.UUID,
    body: DiagramJsonUpdate,
) -> Any:
    """Update the diagram/layout JSON on the latest version."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)

    latest = _latest_version(session, project_id)
    if not latest:
        raise HTTPException(status_code=404, detail="No diagram version found")

    update_data = body.model_dump(exclude_unset=True)
    latest.sqlmodel_update(update_data)
    project.updated_at = datetime.now(timezone.utc)
    session.add(latest)
    session.add(project)
    session.commit()
    session.refresh(latest)
    return DiagramVersionPublic.model_validate(latest)


# ---------------------------------------------------------------------------
# Node CRUD
# ---------------------------------------------------------------------------


def _get_latest_version_or_404(
    session: SessionDep, project_id: uuid.UUID
) -> DiagramVersion:
    dv = _latest_version(session, project_id)
    if not dv:
        raise HTTPException(status_code=404, detail="No diagram version found")
    return dv


@router.post("/{project_id}/diagram/nodes", response_model=DiagramNodePublic)
def add_node(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    project_id: uuid.UUID,
    node_in: DiagramNodeCreate,
) -> Any:
    """Add a node to the latest diagram version."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)
    dv = _get_latest_version_or_404(session, project_id)

    node = DiagramNode.model_validate(node_in, update={"diagram_version_id": dv.id})
    session.add(node)
    project.updated_at = datetime.now(timezone.utc)
    session.add(project)
    session.commit()
    session.refresh(node)
    return node


@router.patch("/{project_id}/diagram/nodes/{node_id}", response_model=DiagramNodePublic)
def update_node(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    project_id: uuid.UUID,
    node_id: uuid.UUID,
    node_in: DiagramNodeUpdate,
) -> Any:
    """Update a diagram node."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)

    node = session.get(DiagramNode, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    dv = session.get(DiagramVersion, node.diagram_version_id)
    if not dv or dv.project_id != project_id:
        raise HTTPException(
            status_code=403, detail="Node does not belong to this project"
        )

    node.sqlmodel_update(node_in.model_dump(exclude_unset=True))
    project.updated_at = datetime.now(timezone.utc)
    session.add(node)
    session.add(project)
    session.commit()
    session.refresh(node)
    return node


@router.delete("/{project_id}/diagram/nodes/{node_id}", response_model=Message)
def delete_node(
    session: SessionDep,
    current_user: CurrentUser,
    project_id: uuid.UUID,
    node_id: uuid.UUID,
) -> Message:
    """Delete a diagram node."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)

    node = session.get(DiagramNode, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    dv = session.get(DiagramVersion, node.diagram_version_id)
    if not dv or dv.project_id != project_id:
        raise HTTPException(
            status_code=403, detail="Node does not belong to this project"
        )

    edges = session.exec(
        select(DiagramEdge).where(
            (DiagramEdge.source_node_id == node_id)
            | (DiagramEdge.target_node_id == node_id)
        )
    ).all()
    for edge in edges:
        session.delete(edge)
    session.delete(node)
    project.updated_at = datetime.now(timezone.utc)
    session.add(project)
    session.commit()
    return Message(message="Node deleted successfully")


# ---------------------------------------------------------------------------
# Edge CRUD
# ---------------------------------------------------------------------------


@router.post("/{project_id}/diagram/edges", response_model=DiagramEdgePublic)
def add_edge(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    project_id: uuid.UUID,
    edge_in: DiagramEdgeCreate,
) -> Any:
    """Add an edge to the latest diagram version."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)
    dv = _get_latest_version_or_404(session, project_id)

    edge = DiagramEdge.model_validate(edge_in, update={"diagram_version_id": dv.id})
    session.add(edge)
    project.updated_at = datetime.now(timezone.utc)
    session.add(project)
    session.commit()
    session.refresh(edge)
    return edge


@router.patch("/{project_id}/diagram/edges/{edge_id}", response_model=DiagramEdgePublic)
def update_edge(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    project_id: uuid.UUID,
    edge_id: uuid.UUID,
    edge_in: DiagramEdgeUpdate,
) -> Any:
    """Update a diagram edge."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)

    edge = session.get(DiagramEdge, edge_id)
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")
    dv = session.get(DiagramVersion, edge.diagram_version_id)
    if not dv or dv.project_id != project_id:
        raise HTTPException(
            status_code=403, detail="Edge does not belong to this project"
        )

    edge.sqlmodel_update(edge_in.model_dump(exclude_unset=True))
    project.updated_at = datetime.now(timezone.utc)
    session.add(edge)
    session.add(project)
    session.commit()
    session.refresh(edge)
    return edge


@router.delete("/{project_id}/diagram/edges/{edge_id}", response_model=Message)
def delete_edge(
    session: SessionDep,
    current_user: CurrentUser,
    project_id: uuid.UUID,
    edge_id: uuid.UUID,
) -> Message:
    """Delete a diagram edge."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)

    edge = session.get(DiagramEdge, edge_id)
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")
    dv = session.get(DiagramVersion, edge.diagram_version_id)
    if not dv or dv.project_id != project_id:
        raise HTTPException(
            status_code=403, detail="Edge does not belong to this project"
        )

    session.delete(edge)
    project.updated_at = datetime.now(timezone.utc)
    session.add(project)
    session.commit()
    return Message(message="Edge deleted successfully")


# ---------------------------------------------------------------------------
# Export endpoints
# ---------------------------------------------------------------------------


@router.post("/{project_id}/export/markdown")
def export_markdown(
    session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID
) -> Any:
    """Export architecture notes as Markdown."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)

    latest = _latest_version(session, project_id)
    notes = (latest.notes_markdown if latest else None) or "# No notes available"
    return {"format": "markdown", "content": notes}


@router.post("/{project_id}/export/png")
def export_png(
    session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID
) -> Any:
    """Export diagram as PNG (placeholder – returns metadata only)."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)
    return {
        "format": "png",
        "message": "PNG export is not yet implemented. Use the frontend renderer.",
        "project_id": str(project_id),
    }


@router.post("/{project_id}/export/svg")
def export_svg(
    session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID
) -> Any:
    """Export diagram as SVG (placeholder – returns metadata only)."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)
    return {
        "format": "svg",
        "message": "SVG export is not yet implemented. Use the frontend renderer.",
        "project_id": str(project_id),
    }


@router.post("/{project_id}/export/bundle")
def export_bundle(
    session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID
) -> Any:
    """Export a JSON bundle containing project, versions, nodes, edges, and components."""
    project = _get_project_or_404(session, project_id)
    _require_owner(project, current_user)

    latest = _latest_version(session, project_id)
    if not latest:
        prompt_revisions = session.exec(
            select(PromptRevision)
            .where(PromptRevision.project_id == project_id)
            .order_by(col(PromptRevision.created_at).desc())
        ).all()
        return {
            "project": ProjectPublic.model_validate(project).model_dump(),
            "diagram_version": None,
            "prompt_revisions": [
                PromptRevisionPublic.model_validate(revision).model_dump()
                for revision in prompt_revisions
            ],
        }

    nodes = session.exec(
        select(DiagramNode).where(DiagramNode.diagram_version_id == latest.id)
    ).all()
    edges = session.exec(
        select(DiagramEdge).where(DiagramEdge.diagram_version_id == latest.id)
    ).all()
    components = session.exec(
        select(ComponentItem).where(ComponentItem.diagram_version_id == latest.id)
    ).all()
    prompt_revisions = session.exec(
        select(PromptRevision)
        .where(PromptRevision.project_id == project_id)
        .order_by(col(PromptRevision.created_at).desc())
    ).all()

    return {
        "project": ProjectPublic.model_validate(project).model_dump(),
        "diagram_version": DiagramVersionPublic.model_validate(latest).model_dump(),
        "nodes": [DiagramNodePublic.model_validate(n).model_dump() for n in nodes],
        "edges": [DiagramEdgePublic.model_validate(e).model_dump() for e in edges],
        "components": [
            ComponentItemPublic.model_validate(c).model_dump() for c in components
        ],
        "prompt_revisions": [
            PromptRevisionPublic.model_validate(revision).model_dump()
            for revision in prompt_revisions
        ],
    }

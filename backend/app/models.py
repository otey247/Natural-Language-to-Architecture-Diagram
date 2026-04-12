import uuid
from datetime import datetime, timezone

from pydantic import EmailStr
from sqlalchemy import DateTime, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore[assignment]
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)
    projects: list["Project"] = Relationship(
        back_populates="owner", cascade_delete=True
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore[assignment]


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


# ---------------------------------------------------------------------------
# Project models
# ---------------------------------------------------------------------------


class ProjectBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    current_prompt: str | None = Field(default=None, max_length=4096)
    cloud_context: str | None = Field(default=None, max_length=255)
    diagram_type: str | None = Field(default=None, max_length=255)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    current_prompt: str | None = Field(default=None, max_length=4096)
    cloud_context: str | None = Field(default=None, max_length=255)
    diagram_type: str | None = Field(default=None, max_length=255)


class Project(ProjectBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner: User | None = Relationship(back_populates="projects")
    prompt_revisions: list["PromptRevision"] = Relationship(
        back_populates="project", cascade_delete=True
    )
    diagram_versions: list["DiagramVersion"] = Relationship(
        back_populates="project", cascade_delete=True
    )


class ProjectPublic(ProjectBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectsPublic(SQLModel):
    data: list[ProjectPublic]
    count: int


# ---------------------------------------------------------------------------
# PromptRevision models
# ---------------------------------------------------------------------------


class PromptRevisionBase(SQLModel):
    prompt_text: str = Field(min_length=1, max_length=4096)


class PromptRevision(PromptRevisionBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(
        foreign_key="project.id", nullable=False, ondelete="CASCADE"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_by: uuid.UUID | None = None
    project: Project | None = Relationship(back_populates="prompt_revisions")


class PromptRevisionPublic(PromptRevisionBase):
    id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# DiagramVersion models
# ---------------------------------------------------------------------------


class DiagramVersionBase(SQLModel):
    version_number: int = Field(default=1)
    diagram_json: str | None = Field(default=None)
    layout_json: str | None = Field(default=None)
    notes_markdown: str | None = Field(default=None)


class DiagramVersion(DiagramVersionBase, table=True):
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "version_number",
            name="uq_diagramversion_project_id_version_number",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(
        foreign_key="project.id", nullable=False, ondelete="CASCADE"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_by: uuid.UUID | None = None
    project: Project | None = Relationship(back_populates="diagram_versions")
    nodes: list["DiagramNode"] = Relationship(
        back_populates="diagram_version", cascade_delete=True
    )
    edges: list["DiagramEdge"] = Relationship(
        back_populates="diagram_version", cascade_delete=True
    )
    components: list["ComponentItem"] = Relationship(
        back_populates="diagram_version", cascade_delete=True
    )


class DiagramVersionPublic(DiagramVersionBase):
    id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime | None = None


class DiagramVersionsPublic(SQLModel):
    data: list[DiagramVersionPublic]
    count: int


# ---------------------------------------------------------------------------
# DiagramNode models
# ---------------------------------------------------------------------------


class DiagramNodeBase(SQLModel):
    label: str = Field(min_length=1, max_length=255)
    node_type: str = Field(max_length=255)
    provider: str | None = Field(default=None, max_length=255)
    metadata_json: str | None = Field(default=None)
    x_position: float = Field(default=0.0)
    y_position: float = Field(default=0.0)


class DiagramNodeCreate(DiagramNodeBase):
    pass


class DiagramNodeUpdate(SQLModel):
    label: str | None = Field(default=None, min_length=1, max_length=255)
    node_type: str | None = Field(default=None, max_length=255)
    provider: str | None = Field(default=None, max_length=255)
    metadata_json: str | None = Field(default=None)
    x_position: float | None = None
    y_position: float | None = None


class DiagramNode(DiagramNodeBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    diagram_version_id: uuid.UUID = Field(
        foreign_key="diagramversion.id", nullable=False, ondelete="CASCADE"
    )
    diagram_version: DiagramVersion | None = Relationship(back_populates="nodes")


class DiagramNodePublic(DiagramNodeBase):
    id: uuid.UUID
    diagram_version_id: uuid.UUID


# ---------------------------------------------------------------------------
# DiagramEdge models
# ---------------------------------------------------------------------------


class DiagramEdgeBase(SQLModel):
    source_node_id: uuid.UUID = Field(
        foreign_key="diagramnode.id", ondelete="CASCADE", index=True
    )
    target_node_id: uuid.UUID = Field(
        foreign_key="diagramnode.id", ondelete="CASCADE", index=True
    )
    label: str | None = Field(default=None, max_length=255)
    metadata_json: str | None = Field(default=None)


class DiagramEdgeCreate(DiagramEdgeBase):
    pass


class DiagramEdgeUpdate(SQLModel):
    label: str | None = Field(default=None, max_length=255)
    metadata_json: str | None = Field(default=None)


class DiagramEdge(DiagramEdgeBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    diagram_version_id: uuid.UUID = Field(
        foreign_key="diagramversion.id", nullable=False, ondelete="CASCADE"
    )
    diagram_version: DiagramVersion | None = Relationship(back_populates="edges")


class DiagramEdgePublic(DiagramEdgeBase):
    id: uuid.UUID
    diagram_version_id: uuid.UUID


# ---------------------------------------------------------------------------
# ComponentItem models
# ---------------------------------------------------------------------------


class ComponentItemBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    component_type: str = Field(max_length=255)
    provider: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1024)
    role_summary: str | None = Field(default=None, max_length=1024)


class ComponentItemCreate(ComponentItemBase):
    pass


class ComponentItem(ComponentItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    diagram_version_id: uuid.UUID = Field(
        foreign_key="diagramversion.id", nullable=False, ondelete="CASCADE"
    )
    diagram_version: DiagramVersion | None = Relationship(back_populates="components")


class ComponentItemPublic(ComponentItemBase):
    id: uuid.UUID
    diagram_version_id: uuid.UUID


# ---------------------------------------------------------------------------
# Generation request / result
# ---------------------------------------------------------------------------


class GenerationRequest(SQLModel):
    prompt: str = Field(min_length=1, max_length=4096)
    cloud_context: str | None = None
    diagram_type: str | None = None


class GenerationResult(SQLModel):
    diagram_version: DiagramVersionPublic
    nodes: list[DiagramNodePublic]
    edges: list[DiagramEdgePublic]
    components: list[ComponentItemPublic]
    notes_markdown: str


# ---------------------------------------------------------------------------
# Diagram JSON update
# ---------------------------------------------------------------------------


class DiagramJsonUpdate(SQLModel):
    diagram_json: str | None = None
    layout_json: str | None = None
    notes_markdown: str | None = None

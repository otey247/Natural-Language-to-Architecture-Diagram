"""Tests for the /projects routes."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.models import (
    ComponentItem,
    DiagramEdge,
    DiagramNode,
    DiagramVersion,
    Project,
    PromptRevision,
    User,
)
from tests.utils.user import create_random_user, authentication_token_from_email
from tests.utils.utils import random_lower_string, get_superuser_token_headers

BASE = f"{settings.API_V1_STR}/projects"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def normal_user(db: Session) -> User:
    return create_random_user(db)


@pytest.fixture()
def normal_user_headers(client: TestClient, normal_user: User, db: Session) -> dict[str, str]:
    from tests.utils.user import user_authentication_headers
    from app.models import UserUpdate
    from app import crud

    new_password = random_lower_string()
    crud.update_user(session=db, db_user=normal_user, user_in=UserUpdate(password=new_password))
    return user_authentication_headers(
        client=client, email=normal_user.email, password=new_password
    )


def _create_project(client: TestClient, headers: dict, title: str | None = None) -> dict:
    payload = {"title": title or random_lower_string(), "description": "Test project"}
    resp = client.post(BASE + "/", headers=headers, json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

class TestProjectCreate:
    def test_create_project(self, client: TestClient, superuser_token_headers: dict) -> None:
        payload = {"title": "My Arch", "description": "Hub-spoke on Azure"}
        resp = client.post(BASE + "/", headers=superuser_token_headers, json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == payload["title"]
        assert "id" in data
        assert "owner_id" in data

    def test_create_project_min_fields(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        resp = client.post(BASE + "/", headers=superuser_token_headers, json={"title": "x"})
        assert resp.status_code == 200

    def test_create_project_title_too_long(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        resp = client.post(
            BASE + "/",
            headers=superuser_token_headers,
            json={"title": "a" * 256},
        )
        assert resp.status_code == 422

    def test_create_project_empty_title(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        resp = client.post(BASE + "/", headers=superuser_token_headers, json={"title": ""})
        assert resp.status_code == 422


class TestProjectRead:
    def test_list_projects(self, client: TestClient, superuser_token_headers: dict) -> None:
        _create_project(client, superuser_token_headers)
        _create_project(client, superuser_token_headers)
        resp = client.get(BASE + "/", headers=superuser_token_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 2
        assert isinstance(data["data"], list)

    def test_get_project(self, client: TestClient, superuser_token_headers: dict) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.get(f"{BASE}/{project['id']}", headers=superuser_token_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == project["id"]

    def test_get_project_not_found(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        resp = client.get(f"{BASE}/{uuid.uuid4()}", headers=superuser_token_headers)
        assert resp.status_code == 404

    def test_get_project_forbidden(
        self,
        client: TestClient,
        superuser_token_headers: dict,
        normal_user_headers: dict,
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.get(f"{BASE}/{project['id']}", headers=normal_user_headers)
        assert resp.status_code == 403


class TestProjectUpdate:
    def test_update_project(self, client: TestClient, superuser_token_headers: dict) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.patch(
            f"{BASE}/{project['id']}",
            headers=superuser_token_headers,
            json={"title": "Updated Title", "cloud_context": "azure"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Title"
        assert data["cloud_context"] == "azure"

    def test_update_project_not_found(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        resp = client.patch(
            f"{BASE}/{uuid.uuid4()}",
            headers=superuser_token_headers,
            json={"title": "x"},
        )
        assert resp.status_code == 404

    def test_update_project_forbidden(
        self,
        client: TestClient,
        superuser_token_headers: dict,
        normal_user_headers: dict,
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.patch(
            f"{BASE}/{project['id']}",
            headers=normal_user_headers,
            json={"title": "Hacked"},
        )
        assert resp.status_code == 403


class TestProjectDelete:
    def test_delete_project(self, client: TestClient, superuser_token_headers: dict) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.delete(f"{BASE}/{project['id']}", headers=superuser_token_headers)
        assert resp.status_code == 200
        assert resp.json()["message"] == "Project deleted successfully"

        resp2 = client.get(f"{BASE}/{project['id']}", headers=superuser_token_headers)
        assert resp2.status_code == 404

    def test_delete_project_not_found(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        resp = client.delete(f"{BASE}/{uuid.uuid4()}", headers=superuser_token_headers)
        assert resp.status_code == 404

    def test_delete_project_forbidden(
        self,
        client: TestClient,
        superuser_token_headers: dict,
        normal_user_headers: dict,
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.delete(f"{BASE}/{project['id']}", headers=normal_user_headers)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Project duplicate
# ---------------------------------------------------------------------------

class TestProjectDuplicate:
    def test_duplicate_project(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers, title="Original")
        resp = client.post(
            f"{BASE}/{project['id']}/duplicate", headers=superuser_token_headers
        )
        assert resp.status_code == 200
        copy = resp.json()
        assert copy["title"] == "Original (copy)"
        assert copy["id"] != project["id"]

    def test_duplicate_not_found(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        resp = client.post(f"{BASE}/{uuid.uuid4()}/duplicate", headers=superuser_token_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

class TestGenerate:
    def test_generate_azure_hub_spoke(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.post(
            f"{BASE}/{project['id']}/generate",
            headers=superuser_token_headers,
            json={
                "prompt": "Azure hub and spoke with firewall, app gateway, AKS, private endpoints, and SQL"
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "diagram_version" in data
        assert "nodes" in data
        assert "edges" in data
        assert "components" in data
        assert len(data["nodes"]) > 0
        assert data["notes_markdown"] != ""

    def test_generate_aws_serverless(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.post(
            f"{BASE}/{project['id']}/generate",
            headers=superuser_token_headers,
            json={
                "prompt": "AWS serverless event-driven order processing with Lambda, API Gateway, SQS, DynamoDB"
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) > 0

    def test_generate_three_tier(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.post(
            f"{BASE}/{project['id']}/generate",
            headers=superuser_token_headers,
            json={
                "prompt": "3-tier web application with load balancer, app server, and database"
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) > 0

    def test_generate_increments_version(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        prompt = {"prompt": "AKS with SQL and Redis"}
        r1 = client.post(
            f"{BASE}/{project['id']}/generate",
            headers=superuser_token_headers,
            json=prompt,
        )
        r2 = client.post(
            f"{BASE}/{project['id']}/generate",
            headers=superuser_token_headers,
            json=prompt,
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        v1 = r1.json()["diagram_version"]["version_number"]
        v2 = r2.json()["diagram_version"]["version_number"]
        assert v2 > v1

    def test_generate_not_found(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        resp = client.post(
            f"{BASE}/{uuid.uuid4()}/generate",
            headers=superuser_token_headers,
            json={"prompt": "test"},
        )
        assert resp.status_code == 404

    def test_generate_forbidden(
        self,
        client: TestClient,
        superuser_token_headers: dict,
        normal_user_headers: dict,
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.post(
            f"{BASE}/{project['id']}/generate",
            headers=normal_user_headers,
            json={"prompt": "test"},
        )
        assert resp.status_code == 403


class TestRefine:
    def test_refine_diagram(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        client.post(
            f"{BASE}/{project['id']}/generate",
            headers=superuser_token_headers,
            json={"prompt": "AWS Lambda with DynamoDB"},
        )
        resp = client.post(
            f"{BASE}/{project['id']}/refine",
            headers=superuser_token_headers,
            json={"prompt": "Add SQS queue and monitoring"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) > 0

    def test_refine_not_found(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        resp = client.post(
            f"{BASE}/{uuid.uuid4()}/refine",
            headers=superuser_token_headers,
            json={"prompt": "add cache"},
        )
        assert resp.status_code == 404


class TestRegenerateNotes:
    def test_regenerate_notes(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        client.post(
            f"{BASE}/{project['id']}/generate",
            headers=superuser_token_headers,
            json={"prompt": "Azure AKS with SQL"},
        )
        resp = client.post(
            f"{BASE}/{project['id']}/regenerate-notes",
            headers=superuser_token_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Notes regenerated successfully"

    def test_regenerate_notes_no_version(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.post(
            f"{BASE}/{project['id']}/regenerate-notes",
            headers=superuser_token_headers,
        )
        assert resp.status_code == 404


class TestRegenerateComponents:
    def test_regenerate_components(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        client.post(
            f"{BASE}/{project['id']}/generate",
            headers=superuser_token_headers,
            json={"prompt": "Azure AKS with SQL and Redis"},
        )
        resp = client.post(
            f"{BASE}/{project['id']}/regenerate-components",
            headers=superuser_token_headers,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_regenerate_components_no_version(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.post(
            f"{BASE}/{project['id']}/regenerate-components",
            headers=superuser_token_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Version management
# ---------------------------------------------------------------------------

class TestVersions:
    def test_list_versions(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        for _ in range(2):
            client.post(
                f"{BASE}/{project['id']}/generate",
                headers=superuser_token_headers,
                json={"prompt": "AKS with SQL"},
            )
        resp = client.get(
            f"{BASE}/{project['id']}/versions", headers=superuser_token_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 2

    def test_restore_version(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        gen = client.post(
            f"{BASE}/{project['id']}/generate",
            headers=superuser_token_headers,
            json={"prompt": "AKS with SQL"},
        )
        version_id = gen.json()["diagram_version"]["id"]
        resp = client.post(
            f"{BASE}/{project['id']}/versions/{version_id}/restore",
            headers=superuser_token_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["version_number"] >= 2

    def test_restore_version_not_found(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.post(
            f"{BASE}/{project['id']}/versions/{uuid.uuid4()}/restore",
            headers=superuser_token_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Diagram JSON update
# ---------------------------------------------------------------------------

class TestDiagramUpdate:
    def test_update_diagram_json(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        client.post(
            f"{BASE}/{project['id']}/generate",
            headers=superuser_token_headers,
            json={"prompt": "AKS"},
        )
        resp = client.patch(
            f"{BASE}/{project['id']}/diagram",
            headers=superuser_token_headers,
            json={"diagram_json": '{"nodes":[]}', "notes_markdown": "updated notes"},
        )
        assert resp.status_code == 200

    def test_update_diagram_no_version(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.patch(
            f"{BASE}/{project['id']}/diagram",
            headers=superuser_token_headers,
            json={"diagram_json": "{}"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Node CRUD
# ---------------------------------------------------------------------------

class TestNodeCrud:
    def _setup(
        self, client: TestClient, headers: dict
    ) -> tuple[str, str]:
        """Return (project_id, diagram_version_id)."""
        project = _create_project(client, headers)
        gen = client.post(
            f"{BASE}/{project['id']}/generate",
            headers=headers,
            json={"prompt": "AKS with SQL"},
        )
        dv_id = gen.json()["diagram_version"]["id"]
        return project["id"], dv_id

    def test_add_node(self, client: TestClient, superuser_token_headers: dict) -> None:
        pid, _ = self._setup(client, superuser_token_headers)
        resp = client.post(
            f"{BASE}/{pid}/diagram/nodes",
            headers=superuser_token_headers,
            json={
                "label": "New Node",
                "node_type": "vm",
                "x_position": 100.0,
                "y_position": 200.0,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["label"] == "New Node"
        assert "id" in data

    def test_add_node_no_version(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.post(
            f"{BASE}/{project['id']}/diagram/nodes",
            headers=superuser_token_headers,
            json={"label": "x", "node_type": "vm", "x_position": 0, "y_position": 0},
        )
        assert resp.status_code == 404

    def test_update_node(self, client: TestClient, superuser_token_headers: dict) -> None:
        pid, _ = self._setup(client, superuser_token_headers)
        add_resp = client.post(
            f"{BASE}/{pid}/diagram/nodes",
            headers=superuser_token_headers,
            json={"label": "Old", "node_type": "vm", "x_position": 0, "y_position": 0},
        )
        node_id = add_resp.json()["id"]
        resp = client.patch(
            f"{BASE}/{pid}/diagram/nodes/{node_id}",
            headers=superuser_token_headers,
            json={"label": "Updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["label"] == "Updated"

    def test_update_node_not_found(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.patch(
            f"{BASE}/{project['id']}/diagram/nodes/{uuid.uuid4()}",
            headers=superuser_token_headers,
            json={"label": "x"},
        )
        assert resp.status_code == 404

    def test_delete_node(self, client: TestClient, superuser_token_headers: dict) -> None:
        pid, _ = self._setup(client, superuser_token_headers)
        add_resp = client.post(
            f"{BASE}/{pid}/diagram/nodes",
            headers=superuser_token_headers,
            json={"label": "TempNode", "node_type": "vm", "x_position": 0, "y_position": 0},
        )
        node_id = add_resp.json()["id"]
        resp = client.delete(
            f"{BASE}/{pid}/diagram/nodes/{node_id}", headers=superuser_token_headers
        )
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"]

    def test_delete_node_not_found(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.delete(
            f"{BASE}/{project['id']}/diagram/nodes/{uuid.uuid4()}",
            headers=superuser_token_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Edge CRUD
# ---------------------------------------------------------------------------

class TestEdgeCrud:
    def _setup_with_nodes(
        self, client: TestClient, headers: dict
    ) -> tuple[str, str, str]:
        """Return (project_id, node_id_1, node_id_2)."""
        project = _create_project(client, headers)
        gen = client.post(
            f"{BASE}/{project['id']}/generate",
            headers=headers,
            json={"prompt": "AKS with SQL"},
        )
        assert gen.status_code == 200
        pid = project["id"]
        n1 = client.post(
            f"{BASE}/{pid}/diagram/nodes",
            headers=headers,
            json={"label": "N1", "node_type": "vm", "x_position": 0, "y_position": 0},
        ).json()["id"]
        n2 = client.post(
            f"{BASE}/{pid}/diagram/nodes",
            headers=headers,
            json={"label": "N2", "node_type": "database", "x_position": 100, "y_position": 0},
        ).json()["id"]
        return pid, n1, n2

    def test_add_edge(self, client: TestClient, superuser_token_headers: dict) -> None:
        pid, n1, n2 = self._setup_with_nodes(client, superuser_token_headers)
        resp = client.post(
            f"{BASE}/{pid}/diagram/edges",
            headers=superuser_token_headers,
            json={"source_node_id": n1, "target_node_id": n2, "label": "connects"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_node_id"] == n1
        assert data["target_node_id"] == n2

    def test_update_edge(self, client: TestClient, superuser_token_headers: dict) -> None:
        pid, n1, n2 = self._setup_with_nodes(client, superuser_token_headers)
        edge = client.post(
            f"{BASE}/{pid}/diagram/edges",
            headers=superuser_token_headers,
            json={"source_node_id": n1, "target_node_id": n2},
        ).json()
        resp = client.patch(
            f"{BASE}/{pid}/diagram/edges/{edge['id']}",
            headers=superuser_token_headers,
            json={"label": "updated-label"},
        )
        assert resp.status_code == 200
        assert resp.json()["label"] == "updated-label"

    def test_update_edge_not_found(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.patch(
            f"{BASE}/{project['id']}/diagram/edges/{uuid.uuid4()}",
            headers=superuser_token_headers,
            json={"label": "x"},
        )
        assert resp.status_code == 404

    def test_delete_edge(self, client: TestClient, superuser_token_headers: dict) -> None:
        pid, n1, n2 = self._setup_with_nodes(client, superuser_token_headers)
        edge = client.post(
            f"{BASE}/{pid}/diagram/edges",
            headers=superuser_token_headers,
            json={"source_node_id": n1, "target_node_id": n2},
        ).json()
        resp = client.delete(
            f"{BASE}/{pid}/diagram/edges/{edge['id']}", headers=superuser_token_headers
        )
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"]

    def test_delete_edge_not_found(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.delete(
            f"{BASE}/{project['id']}/diagram/edges/{uuid.uuid4()}",
            headers=superuser_token_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Export endpoints
# ---------------------------------------------------------------------------

class TestExport:
    def _project_with_gen(
        self, client: TestClient, headers: dict
    ) -> dict:
        project = _create_project(client, headers)
        client.post(
            f"{BASE}/{project['id']}/generate",
            headers=headers,
            json={"prompt": "Azure AKS with SQL and Redis"},
        )
        return project

    def test_export_markdown(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = self._project_with_gen(client, superuser_token_headers)
        resp = client.post(
            f"{BASE}/{project['id']}/export/markdown", headers=superuser_token_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "markdown"
        assert "content" in data
        assert len(data["content"]) > 0

    def test_export_markdown_empty_project(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.post(
            f"{BASE}/{project['id']}/export/markdown", headers=superuser_token_headers
        )
        assert resp.status_code == 200
        assert "No notes" in resp.json()["content"]

    def test_export_png(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = self._project_with_gen(client, superuser_token_headers)
        resp = client.post(
            f"{BASE}/{project['id']}/export/png", headers=superuser_token_headers
        )
        assert resp.status_code == 200
        assert resp.json()["format"] == "png"

    def test_export_svg(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = self._project_with_gen(client, superuser_token_headers)
        resp = client.post(
            f"{BASE}/{project['id']}/export/svg", headers=superuser_token_headers
        )
        assert resp.status_code == 200
        assert resp.json()["format"] == "svg"

    def test_export_bundle(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = self._project_with_gen(client, superuser_token_headers)
        resp = client.post(
            f"{BASE}/{project['id']}/export/bundle", headers=superuser_token_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "project" in data
        assert "nodes" in data
        assert "edges" in data
        assert "components" in data

    def test_export_bundle_empty_project(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.post(
            f"{BASE}/{project['id']}/export/bundle", headers=superuser_token_headers
        )
        assert resp.status_code == 200
        assert resp.json()["diagram_version"] is None

    def test_export_not_found(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        resp = client.post(
            f"{BASE}/{uuid.uuid4()}/export/markdown", headers=superuser_token_headers
        )
        assert resp.status_code == 404

    def test_export_forbidden(
        self,
        client: TestClient,
        superuser_token_headers: dict,
        normal_user_headers: dict,
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.post(
            f"{BASE}/{project['id']}/export/markdown", headers=normal_user_headers
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Permission/ownership checks
# ---------------------------------------------------------------------------

class TestPermissions:
    def test_normal_user_can_create_and_read_own_project(
        self, client: TestClient, normal_user_headers: dict
    ) -> None:
        project = _create_project(client, normal_user_headers)
        resp = client.get(f"{BASE}/{project['id']}", headers=normal_user_headers)
        assert resp.status_code == 200

    def test_normal_user_cannot_see_others_project(
        self,
        client: TestClient,
        superuser_token_headers: dict,
        normal_user_headers: dict,
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.get(f"{BASE}/{project['id']}", headers=normal_user_headers)
        assert resp.status_code == 403

    def test_superuser_can_see_own_projects(
        self, client: TestClient, superuser_token_headers: dict
    ) -> None:
        project = _create_project(client, superuser_token_headers)
        resp = client.get(f"{BASE}/{project['id']}", headers=superuser_token_headers)
        assert resp.status_code == 200

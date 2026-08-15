from collections.abc import Generator
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.documents.router as document_router
from app.config import Settings
from app.database import get_session
from app.graphs.db_models import GraphRevisionRecord
from app.main import app


def upload_demo_document(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[str, dict]:
    monkeypatch.setattr(
        document_router,
        "settings",
        Settings(database_url="sqlite://", storage_dir=tmp_path, demo_mock_graph=True),
    )
    created = client.post(
        "/documents", json={"name": "diagram.png", "sourceType": "image"}
    ).json()
    output = BytesIO()
    Image.new("RGB", (20, 10), "white").save(output, format="PNG")
    uploaded = client.post(
        f"/documents/{created['id']}/upload",
        files={"file": ("diagram.png", output.getvalue(), "image/png")},
    )
    assert uploaded.status_code == 200
    return created["id"], uploaded.json()


def test_empty_graph_is_returned_when_demo_seeding_is_disabled(client: TestClient) -> None:
    created = client.post(
        "/documents", json={"name": "empty.png", "sourceType": "image"}
    ).json()

    response = client.get(f"/documents/{created['id']}/graph")

    assert response.status_code == 200
    assert response.json()["entities"] == []
    assert response.json()["connections"] == []


def test_demo_seed_is_persisted_and_idempotent(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document_id, _ = upload_demo_document(client, tmp_path, monkeypatch)

    first = client.get(f"/documents/{document_id}/graph").json()
    second = client.get(f"/documents/{document_id}/graph").json()

    assert len(first["entities"]) == 4
    assert len(first["connections"]) == 2
    assert second == first
    assert all(entity["documentId"] == document_id for entity in first["entities"])


def test_demo_seed_ids_do_not_collide_across_documents(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_id, _ = upload_demo_document(client, tmp_path, monkeypatch)
    second_id, _ = upload_demo_document(client, tmp_path, monkeypatch)

    first = client.get(f"/documents/{first_id}/graph").json()
    second = client.get(f"/documents/{second_id}/graph").json()

    assert len(second["entities"]) == 4
    assert {entity["id"] for entity in first["entities"]}.isdisjoint(
        entity["id"] for entity in second["entities"]
    )


def test_patch_persists_fields_and_creates_field_revisions(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document_id, _ = upload_demo_document(client, tmp_path, monkeypatch)

    graph = client.get(f"/documents/{document_id}/graph").json()
    entity_id = next(entity["id"] for entity in graph["entities"] if entity["tag"] == "P-MOCK-1")
    response = client.patch(
        f"/entities/{entity_id}",
        json={
            "tag": "P-EDITED",
            "displayName": "Edited pump",
            "properties": {"service": "water", "stages": 2},
            "assertion": {"reviewStatus": "corrected"},
        },
    )

    assert response.status_code == 200
    assert response.json()["tag"] == "P-EDITED"
    assert response.json()["displayName"] == "Edited pump"
    assert response.json()["assertion"]["reviewStatus"] == "corrected"
    refreshed = client.get(f"/documents/{document_id}/graph").json()
    saved = next(entity for entity in refreshed["entities"] if entity["id"] == entity_id)
    assert saved["tag"] == "P-EDITED"
    assert saved["properties"] == {"service": "water", "stages": 2}

    revisions = revision_rows()
    assert {revision.field_path for revision in revisions} == {
        "tag", "displayName", "properties", "assertion.reviewStatus"
    }
    assert all(revision.actor_type == "user" for revision in revisions)
    assert all(revision.document_id == document_id for revision in revisions)


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "not-a-kind"},
        {"assertion": {"reviewStatus": "approved"}},
        {"properties": "not-an-object"},
        {"id": "changed-id"},
        {"documentId": "changed-document"},
        {"pageId": "changed-page"},
    ],
)
def test_patch_rejects_invalid_or_immutable_fields(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: dict,
) -> None:
    document_id, _ = upload_demo_document(client, tmp_path, monkeypatch)
    graph = client.get(f"/documents/{document_id}/graph").json()
    entity_id = graph["entities"][0]["id"]

    response = client.patch(f"/entities/{entity_id}", json=payload)

    assert response.status_code == 422


def revision_rows() -> list[GraphRevisionRecord]:
    dependency = app.dependency_overrides[get_session]
    generator: Generator[Session, None, None] = dependency()
    session = next(generator)
    try:
        return list(session.scalars(select(GraphRevisionRecord)).all())
    finally:
        generator.close()

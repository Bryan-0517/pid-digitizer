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


def connection_payload(source_id: str, target_id: str, **overrides: object) -> dict:
    payload = {
        "sourceEntityId": source_id,
        "targetEntityId": target_id,
        "kind": "signal",
        "medium": "electrical",
        "direction": "source_to_target",
        "properties": {"service": "status"},
        "assertion": {"reviewStatus": "unreviewed"},
        "allowSelfLoop": False,
    }
    payload.update(overrides)
    return payload


def test_connection_create_update_delete_persists_and_revises(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document_id, _ = upload_demo_document(client, tmp_path, monkeypatch)
    entities = client.get(f"/documents/{document_id}/graph").json()["entities"]

    created_response = client.post(
        f"/documents/{document_id}/connections",
        json=connection_payload(entities[0]["id"], entities[1]["id"]),
    )
    assert created_response.status_code == 201
    created = created_response.json()
    assert created["geometry"] is None
    assert created["assertion"]["mode"] == "human_added"
    assert created["provenance"] == []

    updated_response = client.patch(
        f"/connections/{created['id']}",
        json={
            "targetEntityId": entities[2]["id"],
            "medium": "data",
            "properties": {"protocol": "digital"},
            "assertion": {"reviewStatus": "confirmed"},
        },
    )
    assert updated_response.status_code == 200
    assert updated_response.json()["targetEntityId"] == entities[2]["id"]
    assert updated_response.json()["assertion"]["reviewStatus"] == "confirmed"

    refreshed = client.get(f"/documents/{document_id}/graph").json()
    persisted = next(item for item in refreshed["connections"] if item["id"] == created["id"])
    assert persisted["medium"] == "data"
    assert persisted["properties"] == {"protocol": "digital"}

    deleted_response = client.delete(f"/connections/{created['id']}")
    assert deleted_response.status_code == 204
    assert all(
        item["id"] != created["id"]
        for item in client.get(f"/documents/{document_id}/graph").json()["connections"]
    )

    revisions = [row for row in revision_rows() if row.object_id == created["id"]]
    assert [row.operation for row in revisions] == [
        "create", "update", "update", "update", "update", "delete"
    ]
    assert revisions[0].before is None
    assert revisions[0].after["id"] == created["id"]
    assert {row.field_path for row in revisions[1:-1]} == {
        "targetEntityId", "medium", "properties", "assertion.reviewStatus"
    }
    assert revisions[-1].before["id"] == created["id"]
    assert revisions[-1].after is None
    assert all(row.actor_type == "user" for row in revisions)


@pytest.mark.parametrize(
    "field,value",
    [
        ("sourceEntityId", "missing-source"),
        ("targetEntityId", "missing-target"),
        ("kind", "invalid-kind"),
        ("direction", "sideways"),
        ("assertion", {"reviewStatus": "approved"}),
        ("properties", "not-an-object"),
        ("id", "immutable"),
        ("documentId", "immutable"),
    ],
)
def test_connection_create_rejects_invalid_fields(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    field: str, value: object,
) -> None:
    document_id, _ = upload_demo_document(client, tmp_path, monkeypatch)
    entities = client.get(f"/documents/{document_id}/graph").json()["entities"]
    payload = connection_payload(entities[0]["id"], entities[1]["id"])
    payload[field] = value
    assert client.post(f"/documents/{document_id}/connections", json=payload).status_code == 422


def test_connection_rejects_cross_document_reference_and_disallowed_self_loop(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_id, _ = upload_demo_document(client, tmp_path, monkeypatch)
    second_id, _ = upload_demo_document(client, tmp_path, monkeypatch)
    first_entities = client.get(f"/documents/{first_id}/graph").json()["entities"]
    second_entity = client.get(f"/documents/{second_id}/graph").json()["entities"][0]

    cross = connection_payload(first_entities[0]["id"], second_entity["id"])
    assert client.post(f"/documents/{first_id}/connections", json=cross).status_code == 422

    loop = connection_payload(first_entities[0]["id"], first_entities[0]["id"])
    assert client.post(f"/documents/{first_id}/connections", json=loop).status_code == 422
    loop["allowSelfLoop"] = True
    accepted = client.post(f"/documents/{first_id}/connections", json=loop)
    assert accepted.status_code == 201
    assert accepted.json()["allowSelfLoop"] is True


def test_connection_patch_revalidates_references_and_immutable_fields(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document_id, _ = upload_demo_document(client, tmp_path, monkeypatch)
    graph = client.get(f"/documents/{document_id}/graph").json()
    connection_id = graph["connections"][0]["id"]

    assert client.patch(
        f"/connections/{connection_id}", json={"targetEntityId": "missing"}
    ).status_code == 422
    assert client.patch(
        f"/connections/{connection_id}", json={"id": "changed"}
    ).status_code == 422
    assert client.patch(
        f"/connections/{connection_id}", json={"documentId": "changed"}
    ).status_code == 422

    other_document_id, _ = upload_demo_document(client, tmp_path, monkeypatch)
    other_entity_id = client.get(
        f"/documents/{other_document_id}/graph"
    ).json()["entities"][0]["id"]
    assert client.patch(
        f"/connections/{connection_id}", json={"targetEntityId": other_entity_id}
    ).status_code == 422

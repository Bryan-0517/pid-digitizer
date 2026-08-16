from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.dexpi.adapter import DexpiAdapter
from app.dexpi.v01_adapter import VersionNeutralDexpiAdapter
from app.domain.models import EngineeringConnection, EngineeringEntity, EngineeringGraph, GraphMetadata
from app.graphs.db_models import GraphRevisionRecord
from app.graphs.repository import entity_record
from app.main import app


def entity(
    entity_id: str,
    kind: str = "equipment",
    *,
    tag: str | None = "P-101",
    mode: str = "observed",
    review_status: str = "confirmed",
    properties: dict | None = None,
    document_id: str = "doc",
    geometry: dict | None = None,
    dexpi: dict | None = None,
) -> EngineeringEntity:
    return EngineeringEntity.model_validate({
        "id": entity_id,
        "documentId": document_id,
        "pageId": f"page-{document_id}",
        "kind": kind,
        "tag": tag,
        "displayName": f"Display {entity_id}",
        "properties": properties or {},
        "geometry": geometry,
        "confidence": 0.8,
        "assertion": {"mode": mode, "reviewStatus": review_status},
        "provenance": [{
            "id": f"evidence-{entity_id}",
            "sourceType": "human",
            "sourceRef": "synthetic-dexpi-test",
        }],
        "dexpi": dexpi,
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    })


def connection(
    connection_id: str,
    source: str,
    target: str,
    kind: str = "process",
    *,
    mode: str = "human_added",
    review_status: str = "corrected",
    direction: str | None = "unknown",
    properties: dict | None = None,
    document_id: str = "doc",
) -> EngineeringConnection:
    return EngineeringConnection.model_validate({
        "id": connection_id,
        "documentId": document_id,
        "sourceEntityId": source,
        "targetEntityId": target,
        "kind": kind,
        "direction": direction,
        "properties": properties or {},
        "confidence": 0.7,
        "assertion": {"mode": mode, "reviewStatus": review_status},
        "provenance": [{
            "id": f"evidence-{connection_id}",
            "sourceType": "human",
            "sourceRef": "synthetic-dexpi-test",
        }],
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    })


def graph(
    entities: list[EngineeringEntity] | None = None,
    connections: list[EngineeringConnection] | None = None,
    *,
    document_id: str = "doc",
) -> EngineeringGraph:
    return EngineeringGraph(
        schema_version="0.1",
        document_id=document_id,
        entities=entities or [],
        connections=connections or [],
        metadata=GraphMetadata(),
    )


def report(test_graph: EngineeringGraph):
    adapter: DexpiAdapter = VersionNeutralDexpiAdapter()
    return adapter.validate_mappable(test_graph)


def test_empty_graph_status_and_preview() -> None:
    result = report(graph())
    assert result.status == "empty"
    assert result.objects == []
    assert result.preview.objects == []
    assert result.target_dexpi_version is None
    assert result.conformance_validated is False


@pytest.mark.parametrize("kind", ["equipment", "valve", "instrument", "boundary"])
def test_supported_entity_kinds(kind: str) -> None:
    item = entity(f"entity-{kind}", kind, tag=None if kind == "boundary" else "TAG-1")
    result = report(graph([item]))
    assert result.status == "supported"
    assert result.objects[0].disposition == "supported"
    assert result.counts.supported_objects == 1


@pytest.mark.parametrize("kind", ["process", "utility", "signal"])
def test_supported_connection_kinds_and_non_directional_values(kind: str) -> None:
    first, second = entity("a"), entity("b", tag="P-102")
    edge = connection("edge", "a", "b", kind, direction=None)
    result = report(graph([first, second], [edge]))
    edge_report = next(item for item in result.objects if item.canonical_id == "edge")
    assert edge_report.disposition == "supported"
    assert next(field for field in edge_report.fields if field.path == "kind").value == kind
    direction_field = next(field for field in edge_report.fields if field.path == "direction")
    assert direction_field.value is None
    assert direction_field.disposition == "supported"
    assert not any(field.reason_code.startswith("blocked") for field in edge_report.fields)


@pytest.mark.parametrize("kind", ["text", "unknown", "value", "future_kind"])
def test_unsupported_and_future_entity_kinds_are_unmapped(kind: str) -> None:
    item = entity("unsupported", "text", tag=None)
    if kind != "text":
        item = item.model_copy(update={"kind": kind})
    test_graph = graph([entity("placeholder")]).model_copy(update={"entities": [item]})
    result = report(test_graph)
    assert result.objects[0].disposition == "unmapped"
    assert all(field.disposition == "unmapped" for field in result.objects[0].fields)
    assert result.status == "partial"


@pytest.mark.parametrize("kind", ["ownership", "reference", "unknown", "future_kind"])
def test_unsupported_and_future_connection_kinds_are_unmapped(kind: str) -> None:
    first, second = entity("a"), entity("b", tag="P-102")
    edge = connection("edge", "a", "b", "unknown")
    edge = edge.model_copy(update={"kind": kind})
    test_graph = graph([first, second]).model_copy(update={"connections": [edge]})
    result = report(test_graph)
    edge_report = next(item for item in result.objects if item.canonical_id == "edge")
    assert edge_report.disposition == "unmapped"
    assert all(field.reason_code == "unmapped_connection_kind" for field in edge_report.fields)


@pytest.mark.parametrize(
    ("mode", "review_status", "disposition", "reason"),
    [
        ("observed", "confirmed", "supported", None),
        ("observed", "corrected", "supported", None),
        ("human_added", "confirmed", "supported", None),
        ("human_added", "corrected", "supported", None),
        ("observed", "unreviewed", "blocked", "blocked_review_unreviewed"),
        ("observed", "needs_source", "blocked", "blocked_review_needs_source"),
        ("observed", "rejected", "blocked", "blocked_review_rejected"),
        ("inferred", "confirmed", "blocked", "blocked_inferred_assertion"),
    ],
)
def test_review_and_assertion_eligibility(
    mode: str, review_status: str, disposition: str, reason: str | None
) -> None:
    result = report(graph([entity("item", mode=mode, review_status=review_status)]))
    item = result.objects[0]
    assert item.disposition == disposition
    if reason:
        assert reason in {field.reason_code for field in item.fields}


@pytest.mark.parametrize("kind", ["equipment", "valve", "instrument"])
def test_missing_required_entity_tag_is_blocked(kind: str) -> None:
    result = report(graph([entity("item", kind, tag="")]))
    item = result.objects[0]
    assert item.disposition == "blocked"
    blocked = next(field for field in item.fields if field.path == "tag")
    assert blocked.reason_code == "blocked_missing_required_tag"


def test_boundary_tag_is_optional() -> None:
    assert report(graph([entity("boundary", "boundary", tag=None)])).status == "supported"


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("source_entity_id", "", "blocked_missing_required_source"),
        ("target_entity_id", "", "blocked_missing_required_target"),
        ("source_entity_id", "missing", "blocked_unresolved_source"),
        ("target_entity_id", "missing", "blocked_unresolved_target"),
    ],
)
def test_connection_endpoint_blocking(field: str, value: str, reason: str) -> None:
    first, second = entity("a"), entity("b", tag="P-102")
    edge = connection("edge", "a", "b").model_copy(update={field: value})
    test_graph = graph([first, second]).model_copy(update={"connections": [edge]})
    edge_report = next(
        item for item in report(test_graph).objects if item.object_type == "connection"
    )
    assert edge_report.disposition == "blocked"
    assert reason in {field.reason_code for field in edge_report.fields}


def test_nested_properties_geometry_and_advisory_dexpi_are_accounted_as_unmapped() -> None:
    original = entity(
        "item",
        properties={"operatingPressure": {"value": 5, "unit": "bar"}},
        geometry={"bbox": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}},
        dexpi={"suggestedClass": "AdvisoryPump", "mappingStatus": "mappable"},
    )
    before = original.model_dump_json()
    item = report(graph([original])).objects[0]
    by_path = {field.path: field for field in item.fields}
    assert item.disposition == "partial"
    assert by_path["properties.operatingPressure.value"].disposition == "unmapped"
    assert by_path["properties.operatingPressure.value"].value == 5
    assert by_path["geometry.bbox.x"].reason_code == "unmapped_geometry"
    assert by_path["dexpi.suggestedClass"].disposition == "unmapped"
    assert item.suggested_class == "AdvisoryPump"
    assert item.original_mapping_status == "mappable"
    assert original.model_dump_json() == before


def test_absent_suggested_class_does_not_block() -> None:
    item = report(graph([entity("item", dexpi=None)])).objects[0]
    assert item.disposition == "supported"
    assert item.suggested_class is None


def flatten_paths(value: object, prefix: str = "") -> set[str]:
    paths: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else key
            paths.add(path)
            paths.update(flatten_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            path = f"{prefix}[{index}]"
            paths.add(path)
            paths.update(flatten_paths(item, path))
    return paths


def test_no_present_canonical_object_field_is_silently_omitted() -> None:
    item = entity(
        "item", properties={"nested": {"flag": True}},
        geometry={"anchorPoints": [{"x": 0.2, "y": 0.3}]},
        dexpi={"suggestedClass": "Advisory"},
    )
    expected = flatten_paths(item.model_dump(by_alias=True, exclude_none=True))
    actual = {field.path for field in report(graph([item])).objects[0].fields}
    assert actual == expected


def test_graph_status_rules_and_mapping_preview() -> None:
    supported = entity("supported")
    partial = entity("partial", tag="P-102", properties={"custom": 1})
    blocked = entity("blocked", tag="P-103", review_status="unreviewed")
    partial_result = report(graph([supported, partial]))
    blocked_result = report(graph([supported, blocked]))
    assert partial_result.status == "partial"
    assert blocked_result.status == "blocked"
    assert [item.canonical_id for item in partial_result.preview.objects] == ["partial", "supported"]
    assert [item.canonical_id for item in blocked_result.preview.objects] == ["supported"]
    assert blocked_result.preview.target_dexpi_version is None
    assert blocked_result.preview.conformant is False


def test_repeated_validation_is_deterministic_and_does_not_mutate_graph() -> None:
    test_graph = graph([
        entity("b", properties={"z": 1, "a": 2}),
        entity("a", tag="P-102"),
    ])
    before = test_graph.model_dump_json()
    first = report(test_graph).model_dump_json()
    second = report(test_graph).model_dump_json()
    assert first == second
    assert test_graph.model_dump_json() == before


def database_session() -> Generator[Session, None, None]:
    dependency = app.dependency_overrides[get_session]
    yield from dependency()


def persist_graph(document_id: str) -> str:
    generator = database_session()
    session = next(generator)
    try:
        item = entity(
            f"entity-{document_id}", document_id=document_id, review_status="confirmed"
        )
        session.add(entity_record(item))
        session.commit()
        return item.id
    finally:
        generator.close()


def test_dexpi_api_success_is_read_only_and_document_isolated(client: TestClient) -> None:
    first_document = client.post(
        "/documents", json={"name": "first.png", "sourceType": "image"}
    ).json()["id"]
    second_document = client.post(
        "/documents", json={"name": "second.png", "sourceType": "image"}
    ).json()["id"]
    first_entity = persist_graph(first_document)
    persist_graph(second_document)
    before = client.get(f"/documents/{first_document}/graph").json()

    response = client.post(f"/documents/{first_document}/dexpi/validate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "supported"
    assert [item["canonicalId"] for item in payload["objects"]] == [first_entity]
    assert payload["counts"]["supportedObjects"] == 1
    assert client.get(f"/documents/{first_document}/graph").json() == before
    generator = database_session()
    session = next(generator)
    try:
        assert session.scalar(select(func.count()).select_from(GraphRevisionRecord)) == 0
    finally:
        generator.close()


def test_dexpi_api_empty_and_missing_document(client: TestClient) -> None:
    document_id = client.post(
        "/documents", json={"name": "empty.png", "sourceType": "image"}
    ).json()["id"]
    empty = client.post(f"/documents/{document_id}/dexpi/validate")
    missing = client.post("/documents/missing/dexpi/validate")
    assert empty.status_code == 200
    assert empty.json()["status"] == "empty"
    assert empty.json()["counts"]["supportedObjects"] == 0
    assert missing.status_code == 404

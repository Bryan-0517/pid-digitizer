from __future__ import annotations

import builtins
import json
import sys
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import app.dexpi.router as dexpi_router
from app.config import Settings
from app.database import get_session
from app.dexpi.export_service import DexpiExportService
from app.dexpi.pydexpi_v1_2_adapter import (
    PydexpiCompatibilityError,
    PydexpiV12Adapter,
    installed_pydexpi_version,
    package_is_compatible,
)
from app.dexpi.v01_adapter import VersionNeutralDexpiAdapter
from app.domain.models import EngineeringConnection, EngineeringEntity, EngineeringGraph, GraphMetadata
from app.graphs.db_models import GraphRevisionRecord
from app.graphs.repository import entity_record
from app.main import app


def entity(
    entity_id: str,
    *,
    kind: str = "equipment",
    subtype: str | None = "centrifugal_pump",
    tag: str = "P-101",
    review_status: str = "confirmed",
    mode: str = "observed",
    properties: dict | None = None,
    suggested_class: str | None = None,
    mapping_status: str | None = None,
    document_id: str = "doc",
) -> EngineeringEntity:
    dexpi = None
    if suggested_class is not None or mapping_status is not None:
        dexpi = {"suggestedClass": suggested_class, "mappingStatus": mapping_status}
    return EngineeringEntity.model_validate({
        "id": entity_id,
        "documentId": document_id,
        "pageId": f"page-{document_id}",
        "kind": kind,
        "subtype": subtype,
        "tag": tag,
        "properties": properties or {},
        "confidence": 0.9,
        "assertion": {"mode": mode, "reviewStatus": review_status},
        "provenance": [{
            "id": f"evidence-{entity_id}", "sourceType": "human",
            "sourceRef": "synthetic-t016-test",
        }],
        "dexpi": dexpi,
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    })


def connection(connection_id: str, source: str, target: str) -> EngineeringConnection:
    return EngineeringConnection.model_validate({
        "id": connection_id, "documentId": "doc", "sourceEntityId": source,
        "targetEntityId": target, "kind": "process", "direction": "source_to_target",
        "properties": {}, "confidence": 0.8,
        "assertion": {"mode": "observed", "reviewStatus": "confirmed"},
        "provenance": [{
            "id": f"evidence-{connection_id}", "sourceType": "human",
            "sourceRef": "synthetic-t016-test",
        }],
        "createdAt": "2026-01-01T00:00:00Z", "updatedAt": "2026-01-01T00:00:00Z",
    })


def graph(
    entities: list[EngineeringEntity] | None = None,
    connections: list[EngineeringConnection] | None = None,
    *,
    document_id: str = "doc",
) -> EngineeringGraph:
    return EngineeringGraph(
        schema_version="0.1", document_id=document_id,
        entities=entities or [], connections=connections or [], metadata=GraphMetadata(),
    )


def test_exact_pinned_package_is_compatible() -> None:
    assert installed_pydexpi_version() == "1.2.0"
    assert package_is_compatible() is True


def test_t015_and_core_startup_do_not_import_pydexpi(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(sys.modules):
        if name == "pydexpi" or name.startswith("pydexpi."):
            sys.modules.pop(name)
    original_import = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object):
        if name == "pydexpi" or name.startswith("pydexpi."):
            raise AssertionError("disabled T015/startup path imported pydexpi")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    result = VersionNeutralDexpiAdapter().validate_mappable(graph())
    assert result.status == "empty"


@pytest.mark.parametrize(
    ("subtype", "suggested_class", "expected_class"),
    [
        ("centrifugal_pump", None, "CentrifugalPump"),
        ("tank", None, "Tank"),
        (None, "CentrifugalPump", "CentrifugalPump"),
        (None, "Tank", "Tank"),
    ],
)
def test_exact_tiny_mapping_constructs_real_public_pydexpi_objects(
    subtype: str | None, suggested_class: str | None, expected_class: str
) -> None:
    item = entity("equipment-1", subtype=subtype, suggested_class=suggested_class)
    artifact = DexpiExportService().export(graph([item]))
    payload = json.loads(artifact.content)
    included = payload["conversionReport"]["includedObjects"]
    assert included[0]["pydexpiClass"] == expected_class
    mapped = payload["pydexpiModel"]["composition"]["conceptualModel"]["composition"][
        "taggedPlantItems"
    ][0]
    assert mapped["id"] == "equipment-1"
    assert mapped["data"]["tagName"] == "P-101"
    assert expected_class[0].lower() + expected_class[1:] in mapped["uri"]
    assert payload["pydexpiVersion"] == "1.2.0"
    assert payload["targetDexpiVersion"] == "1.3"
    assert payload["conformanceValidated"] is False


def test_generic_equipment_instrument_unmapped_entity_and_connections_are_reported() -> None:
    pump = entity("mapped")
    generic = entity("generic", subtype="equipment", tag="E-1")
    instrument = entity("instrument", kind="instrument", subtype="transmitter", tag="FT-1")
    text = entity("text", kind="text", subtype=None, tag="LABEL")
    edge = connection("edge", "mapped", "generic")
    test_graph = graph([pump, generic, instrument, text], [edge])
    report = DexpiExportService().plan(test_graph)
    omitted = {item.canonical_id: item.reason_code for item in report.omitted_objects}
    assert report.status == "ready"
    assert [item.canonical_id for item in report.included_objects] == ["mapped"]
    assert omitted == {
        "edge": "connection_mapping_not_in_t016_subset",
        "generic": "no_exact_t016_mapping",
        "instrument": "no_exact_t016_mapping",
        "text": "t015_unmapped_object",
    }
    assert any(
        item.canonical_id == "edge" and item.path == "direction"
        for item in report.omitted_fields
    )


def test_partial_object_converts_only_explicit_fields_and_lists_every_omission() -> None:
    item = entity(
        "partial", properties={"operatingPressure": {"value": 5}},
        suggested_class="CentrifugalPump", mapping_status="partial",
    )
    before = item.model_dump_json()
    report = DexpiExportService().plan(graph([item]))
    included = report.included_objects[0]
    assert included.converted_field_paths == ["id", "kind", "tag"]
    paths = {field.path for field in report.omitted_fields}
    assert "properties.operatingPressure.value" in paths
    assert "dexpi.mappingStatus" in paths
    assert "dexpi.suggestedClass" in paths
    assert item.model_dump_json() == before


def test_blocked_graph_prevents_whole_export_with_reasons() -> None:
    blocked = entity("blocked", review_status="unreviewed", mode="inferred")
    service = DexpiExportService()
    plan = service.plan(graph([entity("safe"), blocked]))
    assert plan.status == "blocked"
    assert plan.included_objects == []
    assert plan.blocking_objects[0].canonical_id == "blocked"
    assert plan.blocking_objects[0].reason_codes == [
        "blocked_inferred_assertion", "blocked_review_unreviewed"
    ]
    with pytest.raises(PydexpiCompatibilityError):
        service.pydexpi_adapter.export(graph([entity("safe"), blocked]), plan)


def test_empty_and_no_exportable_content_are_deterministic() -> None:
    service = DexpiExportService()
    assert service.plan(graph()).status == "empty"
    generic = graph([entity("generic", subtype="generic")])
    first = service.plan(generic).model_dump_json()
    second = service.plan(generic).model_dump_json()
    assert json.loads(first)["status"] == "no_exportable_content"
    assert first == second


class BrokenClass:
    def __init__(self, **kwargs: object):
        del kwargs
        raise ValueError("construction failed")


class BrokenSerializer:
    def export_to_bytes(self, model: object, indent: int = 2) -> bytes:
        del model, indent
        raise ValueError("serialization failed")


class PassingClass:
    def __init__(self, **kwargs: object):
        self.kwargs = kwargs


def public_api_with(*, equipment: type, serializer: type) -> dict[str, type]:
    return {
        "CentrifugalPump": equipment,
        "Tank": equipment,
        "ConceptualModel": PassingClass,
        "DexpiModel": PassingClass,
        "JsonSerializer": serializer,
    }


@pytest.mark.parametrize(
    "api",
    [
        public_api_with(equipment=BrokenClass, serializer=BrokenSerializer),
        public_api_with(equipment=PassingClass, serializer=BrokenSerializer),
    ],
)
def test_construction_and_serialization_failures_are_normalized(
    monkeypatch: pytest.MonkeyPatch, api: dict[str, type]
) -> None:
    adapter = PydexpiV12Adapter()
    monkeypatch.setattr(adapter, "_load_public_api", lambda: api)
    test_graph = graph([entity("item")])
    plan = adapter.plan(test_graph, VersionNeutralDexpiAdapter().validate_mappable(test_graph))
    with pytest.raises(PydexpiCompatibilityError) as error:
        adapter.export(test_graph, plan)
    assert "public pyDEXPI construction or JSON serialization failed" in str(error.value)


def test_export_bytes_and_report_are_deterministic_and_graph_is_unchanged() -> None:
    test_graph = graph([entity("b", subtype="tank", tag="T-2"), entity("a")])
    before = test_graph.model_dump_json()
    service = DexpiExportService()
    first = service.export(test_graph)
    second = service.export(test_graph)
    assert first.content == second.content
    assert first.report.model_dump_json() == second.report.model_dump_json()
    assert test_graph.model_dump_json() == before


def database_session() -> Generator[Session, None, None]:
    dependency = app.dependency_overrides[get_session]
    yield from dependency()


def persist_entity(document_id: str, *, blocked: bool = False) -> EngineeringEntity:
    generator = database_session()
    session = next(generator)
    try:
        item = entity(
            f"entity-{document_id}", document_id=document_id,
            review_status="unreviewed" if blocked else "confirmed",
            mapping_status="mappable",
        )
        session.add(entity_record(item))
        session.commit()
        return item
    finally:
        generator.close()


def enabled_settings(tmp_path) -> Settings:
    return Settings(
        database_url="sqlite://", storage_dir=tmp_path, demo_mock_graph=False,
        pydexpi_export_enabled=True,
    )


def test_feature_disabled_and_availability(client: TestClient) -> None:
    document_id = client.post(
        "/documents", json={"name": "disabled.png", "sourceType": "image"}
    ).json()["id"]
    availability = client.get(f"/documents/{document_id}/dexpi/export/availability")
    export = client.post(f"/documents/{document_id}/dexpi/export")
    assert availability.status_code == 200
    assert availability.json()["enabled"] is False
    assert availability.json()["available"] is False
    assert export.status_code == 503
    assert export.json()["detail"]["code"] == "pydexpi_export_unavailable"


def test_export_api_download_metadata_is_read_only(
    client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dexpi_router, "settings", enabled_settings(tmp_path))
    document_id = client.post(
        "/documents", json={"name": "export.png", "sourceType": "image"}
    ).json()["id"]
    original = persist_entity(document_id)
    before = client.get(f"/documents/{document_id}/graph").json()

    response = client.post(f"/documents/{document_id}/dexpi/export")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["content-disposition"] == (
        f'attachment; filename="{document_id}.dexpi-1.3.pydexpi.json"'
    )
    assert response.headers["x-pydexpi-version"] == "1.2.0"
    assert response.headers["x-dexpi-target-version"] == "1.3"
    payload = response.json()
    assert payload["conversionReport"]["includedObjects"][0]["canonicalId"] == original.id
    assert payload["conversionReport"]["conformanceValidated"] is False
    assert client.get(f"/documents/{document_id}/graph").json() == before
    assert before["entities"][0]["dexpi"]["mappingStatus"] == "mappable"
    assert before["entities"][0]["assertion"] == {
        "mode": "observed", "reviewStatus": "confirmed"
    }
    generator = database_session()
    session = next(generator)
    try:
        assert session.scalar(select(func.count()).select_from(GraphRevisionRecord)) == 0
    finally:
        generator.close()


def test_export_api_blocked_empty_missing_and_document_isolation(
    client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dexpi_router, "settings", enabled_settings(tmp_path))
    blocked_document = client.post(
        "/documents", json={"name": "blocked.png", "sourceType": "image"}
    ).json()["id"]
    empty_document = client.post(
        "/documents", json={"name": "empty.png", "sourceType": "image"}
    ).json()["id"]
    blocked = persist_entity(blocked_document, blocked=True)

    blocked_response = client.post(f"/documents/{blocked_document}/dexpi/export")
    empty_response = client.post(f"/documents/{empty_document}/dexpi/export")
    missing_response = client.post("/documents/missing/dexpi/export")
    assert blocked_response.status_code == 409
    assert blocked_response.json()["detail"]["blockingObjects"][0]["canonicalId"] == blocked.id
    assert empty_response.status_code == 409
    assert empty_response.json()["detail"]["status"] == "empty"
    assert missing_response.status_code == 404

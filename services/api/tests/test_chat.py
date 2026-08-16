from __future__ import annotations

import asyncio
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.chat.intent import resolve_intent
from app.chat.schemas import ChatRequest
from app.chat.service import ChatService
from app.chat.verbalizer import DeterministicMockVerbalizer
from app.database import get_session
from app.domain.models import EngineeringConnection, EngineeringEntity, EngineeringGraph, GraphMetadata
from app.graphs.db_models import GraphRevisionRecord
from app.graphs.repository import connection_record, entity_record
from app.main import app


def make_entity(entity_id: str, tag: str, *, document_id: str = "doc") -> EngineeringEntity:
    return EngineeringEntity(
        id=entity_id,
        document_id=document_id,
        page_id=f"page-{document_id}",
        kind="equipment",
        tag=tag,
        display_name=f"Display {tag}",
        properties={},
        confidence=0.42,
        assertion={"mode": "inferred", "reviewStatus": "needs_source"},
        provenance=[{
            "id": f"evidence-{entity_id}",
            "sourceType": "human",
            "sourceRef": "synthetic-chat-test",
            "note": "unverified fixture",
        }],
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


def make_connection(
    connection_id: str,
    source: str,
    target: str,
    *,
    direction: str = "source_to_target",
    document_id: str = "doc",
) -> EngineeringConnection:
    return EngineeringConnection(
        id=connection_id,
        document_id=document_id,
        source_entity_id=source,
        target_entity_id=target,
        kind="process",
        direction=direction,
        properties={},
        confidence=0.51,
        assertion={"mode": "inferred", "reviewStatus": "unreviewed"},
        provenance=[{
            "id": f"evidence-{connection_id}",
            "sourceType": "human",
            "sourceRef": "synthetic-chat-test",
        }],
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


def make_graph() -> EngineeringGraph:
    return EngineeringGraph(
        schema_version="0.1",
        document_id="doc",
        entities=[
            make_entity("entity-a", "P-101"),
            make_entity("entity-b", "V-201"),
            make_entity("entity-c", "T-301"),
            make_entity("entity-z", "ISOLATED"),
        ],
        connections=[
            make_connection("connection-a", "entity-a", "entity-b"),
            make_connection("connection-b", "entity-b", "entity-c"),
        ],
        metadata=GraphMetadata(),
    )


@pytest.mark.parametrize(
    ("message", "operation", "references"),
    [
        ("What is connected to P-101?", "neighbors", ("P-101",)),
        ("Show neighbors of P-101", "neighbors", ("P-101",)),
        ("What is upstream of V-201?", "upstream", ("V-201",)),
        ("What is downstream of P-101?", "downstream", ("P-101",)),
        ("Find P-101", "entity_lookup", ("P-101",)),
        ("Look up P-101", "entity_lookup", ("P-101",)),
        ("What is the shortest path from P-101 to T-301?", "shortest_path", ("P-101", "T-301")),
        ("How is P-101 connected to T-301?", "shortest_path", ("P-101", "T-301")),
    ],
)
def test_narrow_intent_patterns(message: str, operation: str, references: tuple[str, ...]) -> None:
    parsed = resolve_intent(message)
    assert parsed is not None
    assert parsed.operation == operation
    assert parsed.references == references


def run_response(service: ChatService, graph: EngineeringGraph, request: ChatRequest):
    return asyncio.run(service.respond(graph, request))


def test_unsupported_and_empty_message_behavior() -> None:
    response = run_response(
        ChatService(), make_graph(), ChatRequest(message="Explain the whole plant")
    )
    assert response.outcome == "unsupported"
    assert response.answer == "This request is outside the supported graph-query patterns."
    with pytest.raises(ValueError):
        ChatRequest(message="   ")


@pytest.mark.parametrize(
    ("message", "operation", "expected_entities", "expected_connections"),
    [
        ("What is connected to P-101?", "neighbors", ["entity-a", "entity-b"], ["connection-a"]),
        ("What is upstream of T-301?", "upstream", ["entity-a", "entity-b", "entity-c"], ["connection-a", "connection-b"]),
        ("What is downstream of P-101?", "downstream", ["entity-a", "entity-b", "entity-c"], ["connection-a", "connection-b"]),
        ("Find P-101", "entity_lookup", ["entity-a"], []),
        ("What is the shortest path from P-101 to T-301?", "shortest_path", ["entity-a", "entity-b", "entity-c"], ["connection-a", "connection-b"]),
    ],
)
def test_chat_operations_are_grounded_in_t013(
    message: str,
    operation: str,
    expected_entities: list[str],
    expected_connections: list[str],
) -> None:
    response = run_response(ChatService(), make_graph(), ChatRequest(message=message))
    assert response.outcome == "ok"
    assert response.resolved_intent.operation == operation
    assert response.supporting_entity_ids == expected_entities
    assert response.supporting_connection_ids == expected_connections
    assert response.highlight.entity_ids == expected_entities
    assert response.highlight.connection_ids == expected_connections
    t013_entity_ids = {item for result in response.query_results for item in result.entity_ids}
    t013_connection_ids = {item for result in response.query_results for item in result.connection_ids}
    assert set(response.supporting_entity_ids) <= t013_entity_ids
    assert set(response.supporting_connection_ids) <= t013_connection_ids


def test_exact_id_resolution_and_missing_reference() -> None:
    service = ChatService()
    by_id = run_response(service, make_graph(), ChatRequest(message="Find entity-a"))
    missing = run_response(service, make_graph(), ChatRequest(message="Find p-101"))
    assert by_id.outcome == "ok"
    assert by_id.supporting_entity_ids == ["entity-a"]
    assert missing.outcome == "not_found"
    assert missing.answer == "The graph does not contain an entity matching 'p-101'."
    assert missing.supporting_entity_ids == []


def test_duplicate_tag_requires_clarification() -> None:
    graph = make_graph()
    graph.entities.append(make_entity("entity-aa", "P-101"))
    response = run_response(ChatService(), graph, ChatRequest(message="Find P-101"))
    assert response.outcome == "clarification_required"
    assert response.supporting_entity_ids == ["entity-a", "entity-aa"]
    assert response.answer == (
        "The reference matches multiple canonical entities. Clarification is required."
    )


def test_no_path_cannot_become_positive_or_be_verbalized() -> None:
    response = run_response(
        ChatService(verbalizer=DeterministicMockVerbalizer()),
        make_graph(),
        ChatRequest(
            message="What is the shortest path from P-101 to ISOLATED?",
            verbalize=True,
        ),
    )
    assert response.outcome == "no_path"
    assert "does not establish a path" in response.answer
    assert response.verbalization_metadata is None
    assert response.supporting_connection_ids == []


def test_uncertainty_metadata_is_preserved() -> None:
    response = run_response(
        ChatService(), make_graph(), ChatRequest(message="What is connected to P-101?")
    )
    entity_warning = next(item for item in response.warnings if item.object_id == "entity-a")
    connection_warning = next(
        item for item in response.warnings if item.object_id == "connection-a"
    )
    assert entity_warning.assertion.mode == "inferred"
    assert entity_warning.assertion.review_status == "needs_source"
    assert entity_warning.confidence == 0.42
    assert entity_warning.provenance[0].source_ref == "synthetic-chat-test"
    assert connection_warning.connection_kind == "process"
    assert connection_warning.original_direction == "source_to_target"
    assert connection_warning.confidence == 0.51


class FailingVerbalizer:
    async def verbalize(self, request: object) -> object:
        del request
        raise RuntimeError("test failure")


def test_verbalization_disabled_mock_and_failure_fallback() -> None:
    disabled = run_response(
        ChatService(verbalizer=FailingVerbalizer()), make_graph(), ChatRequest(message="Find P-101")
    )
    mocked = run_response(
        ChatService(verbalizer=DeterministicMockVerbalizer()),
        make_graph(), ChatRequest(message="Find P-101", verbalize=True)
    )
    failed = run_response(
        ChatService(verbalizer=FailingVerbalizer()),
        make_graph(), ChatRequest(message="Find P-101", verbalize=True)
    )
    assert disabled.answer == "P-101 resolves to canonical entity entity-a."
    assert disabled.verbalization_metadata is None
    assert mocked.answer.startswith("Grounded summary:")
    assert mocked.verbalization_metadata.provider == "mock"
    assert failed.answer == disabled.answer
    assert failed.warnings[-1].code == "verbalization_failed"


def test_repeated_requests_are_byte_deterministic() -> None:
    service = ChatService()
    request = ChatRequest(message="What is downstream of P-101?")
    first = run_response(service, make_graph(), request)
    second = run_response(service, make_graph(), request)
    assert first.model_dump_json() == second.model_dump_json()


def test_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError):
        ChatRequest.model_validate({"message": "Find P-101", "history": []})


def database_session() -> Generator[Session, None, None]:
    dependency = app.dependency_overrides[get_session]
    yield from dependency()


def persist_test_graph(document_id: str) -> tuple[str, str]:
    generator = database_session()
    session = next(generator)
    try:
        first = make_entity(f"entity-a-{document_id}", "P-101", document_id=document_id)
        second = make_entity(f"entity-b-{document_id}", "V-201", document_id=document_id)
        edge = make_connection(
            f"connection-{document_id}", first.id, second.id, document_id=document_id
        )
        session.add_all([entity_record(first), entity_record(second)])
        session.flush()
        session.add(connection_record(edge))
        session.commit()
        return first.id, second.id
    finally:
        generator.close()


def test_chat_api_is_read_only_and_document_isolated(client: TestClient) -> None:
    first_document = client.post(
        "/documents", json={"name": "first.png", "sourceType": "image"}
    ).json()["id"]
    second_document = client.post(
        "/documents", json={"name": "second.png", "sourceType": "image"}
    ).json()["id"]
    first_id, _ = persist_test_graph(first_document)
    persist_test_graph(second_document)
    before = client.get(f"/documents/{first_document}/graph").json()

    first = client.post(f"/documents/{first_document}/chat", json={
        "message": "What is connected to P-101?"
    })
    second = client.post(f"/documents/{first_document}/chat", json={
        "message": "What is connected to P-101?"
    })
    assert first.status_code == 200
    assert first.json() == second.json()
    assert first_id in first.json()["supportingEntityIds"]
    assert client.get(f"/documents/{first_document}/graph").json() == before

    isolated = client.post(f"/documents/{second_document}/chat", json={
        "message": f"Find {first_id}"
    })
    assert isolated.json()["outcome"] == "not_found"
    generator = database_session()
    session = next(generator)
    try:
        assert session.scalar(select(func.count()).select_from(GraphRevisionRecord)) == 0
    finally:
        generator.close()


def test_chat_api_errors(client: TestClient) -> None:
    document_id = client.post(
        "/documents", json={"name": "empty.png", "sourceType": "image"}
    ).json()["id"]
    assert client.post(f"/documents/{document_id}/chat", json={"message": " "}).status_code == 422
    assert client.post("/documents/missing/chat", json={"message": "Find X"}).status_code == 404

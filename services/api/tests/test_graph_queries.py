from __future__ import annotations

from collections.abc import Generator
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.domain.models import EngineeringConnection, EngineeringEntity, EngineeringGraph, GraphMetadata
from app.graph_queries.schemas import (
    DownstreamQuery,
    EntityLookupQuery,
    NeighborsQuery,
    ShortestPathQuery,
    UpstreamQuery,
)
from app.graph_queries.service import GraphQueryService
from app.graphs.db_models import GraphRevisionRecord
from app.graphs.repository import connection_record, entity_record
from app.main import app


def entity(entity_id: str, *, tag: str | None = None, document_id: str = "doc") -> EngineeringEntity:
    return EngineeringEntity(
        id=entity_id,
        document_id=document_id,
        page_id="page",
        kind="equipment",
        tag=tag,
        properties={},
        confidence=0.7,
        assertion={"mode": "inferred", "reviewStatus": "needs_source"},
        provenance=[{
            "id": f"evidence-{entity_id}",
            "sourceType": "human",
            "sourceRef": "synthetic-test-graph",
            "note": "not verified engineering truth",
        }],
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


def connection(
    connection_id: str,
    source: str,
    target: str,
    *,
    kind: str = "process",
    direction: str | None = "source_to_target",
    document_id: str = "doc",
) -> EngineeringConnection:
    return EngineeringConnection(
        id=connection_id,
        document_id=document_id,
        source_entity_id=source,
        target_entity_id=target,
        kind=kind,
        direction=direction,
        properties={},
        confidence=0.6,
        assertion={"mode": "inferred", "reviewStatus": "unreviewed"},
        provenance=[{
            "id": f"evidence-{connection_id}",
            "sourceType": "human",
            "sourceRef": "synthetic-test-graph",
            "note": "direction is unverified",
        }],
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


def graph(
    entity_ids: tuple[str, ...] = ("A", "B", "C", "D"),
    connections: list[EngineeringConnection] | None = None,
) -> EngineeringGraph:
    return EngineeringGraph(
        schema_version="0.1",
        document_id="doc",
        entities=[entity(item, tag=f"TAG-{item}") for item in entity_ids],
        connections=connections or [],
        metadata=GraphMetadata(),
    )


def test_neighbors_include_all_directions_and_preserve_metadata() -> None:
    test_graph = graph(connections=[
        connection("c-directed", "A", "B"),
        connection("c-undirected", "C", "A", kind="signal", direction="undirected"),
        connection("c-unknown", "A", "D", kind="reference", direction="unknown"),
    ])

    result = GraphQueryService().query(
        test_graph, NeighborsQuery(operation="neighbors", entity_id="A")
    )

    assert result.outcome == "ok"
    assert result.entity_ids == ["B", "C", "D"]
    assert result.connection_ids == ["c-directed", "c-undirected", "c-unknown"]
    assert [item.direction for item in result.connections] == [
        "source_to_target", "undirected", "unknown"
    ]
    assert result.connections[0].assertion.review_status == "unreviewed"
    assert result.connections[0].provenance[0].source_ref == "synthetic-test-graph"
    assert result.connections[0].confidence == 0.6


def test_neighbors_connection_kind_filter() -> None:
    test_graph = graph(connections=[
        connection("c-process", "A", "B"),
        connection("c-signal", "A", "C", kind="signal"),
    ])
    result = GraphQueryService().query(test_graph, NeighborsQuery(
        operation="neighbors", entity_id="A", connection_kinds=["signal"]
    ))
    assert result.entity_ids == ["C"]
    assert result.connection_ids == ["c-signal"]
    assert result.applied_filters.connection_kinds == ["signal"]


def test_upstream_downstream_effective_direction_and_exclusions() -> None:
    test_graph = graph(connections=[
        connection("c1", "A", "B"),
        connection("c2", "C", "B", direction="target_to_source"),  # B -> C
        connection("c3", "C", "D", direction="undirected"),
        connection("c4", "D", "A", direction="unknown"),
    ])
    service = GraphQueryService()

    downstream = service.query(
        test_graph, DownstreamQuery(operation="downstream", entity_id="A")
    )
    upstream = service.query(test_graph, UpstreamQuery(operation="upstream", entity_id="C"))

    assert downstream.entity_ids == ["B", "C"]
    assert [path.entity_ids for path in downstream.paths] == [["A", "B"], ["A", "B", "C"]]
    assert upstream.entity_ids == ["A", "B"]
    assert [path.entity_ids for path in upstream.paths] == [["C", "B", "A"], ["C", "B"]]
    assert "c3" not in downstream.connection_ids
    assert "c4" not in upstream.connection_ids


def test_traversal_handles_cycle_and_kind_filter() -> None:
    test_graph = graph(connections=[
        connection("c1", "A", "B"),
        connection("c2", "B", "C"),
        connection("c3", "C", "A"),
        connection("c4", "C", "D", kind="utility"),
    ])
    result = GraphQueryService().query(test_graph, DownstreamQuery(
        operation="downstream", entity_id="A", connection_kinds=["process"]
    ))
    assert result.entity_ids == ["B", "C"]
    assert len(result.paths) == 2


def test_shortest_path_directed_no_path_and_undirected() -> None:
    test_graph = graph(connections=[
        connection("c1", "A", "B"),
        connection("c2", "C", "B"),
        connection("c3", "C", "D", direction="unknown"),
    ])
    service = GraphQueryService()
    directed = service.query(test_graph, ShortestPathQuery(
        operation="shortest_path", source_entity_id="A", target_entity_id="C"
    ))
    undirected = service.query(test_graph, ShortestPathQuery(
        operation="shortest_path", source_entity_id="A", target_entity_id="D",
        direction_mode="undirected",
    ))

    assert directed.outcome == "no_path"
    assert undirected.outcome == "ok"
    assert undirected.paths[0].entity_ids == ["A", "B", "C", "D"]
    assert undirected.paths[0].connection_ids == ["c1", "c2", "c3"]
    assert undirected.connections[-1].direction == "unknown"


def test_shortest_path_deterministic_tie_break_and_cycle() -> None:
    test_graph = graph(entity_ids=("A", "B", "C", "D", "Z"), connections=[
        connection("z-edge", "A", "B"),
        connection("a-edge", "A", "C"),
        connection("to-d-from-b", "B", "D"),
        connection("to-d-from-c", "C", "D"),
        connection("cycle", "D", "A"),
    ])
    request = ShortestPathQuery(
        operation="shortest_path", source_entity_id="A", target_entity_id="D"
    )
    first = GraphQueryService().query(test_graph, request)
    second = GraphQueryService().query(test_graph, request)
    disconnected = GraphQueryService().query(test_graph, ShortestPathQuery(
        operation="shortest_path", source_entity_id="A", target_entity_id="Z"
    ))

    assert first.paths[0].entity_ids == ["A", "B", "D"]
    assert first.model_dump_json() == second.model_dump_json()
    assert disconnected.outcome == "no_path"


def test_lookup_is_exact_and_duplicate_tags_are_ambiguous() -> None:
    test_graph = graph(entity_ids=())
    test_graph.entities = [entity("B", tag="DUP"), entity("A", tag="DUP"), entity("C", tag="Exact")]
    service = GraphQueryService()

    by_id = service.query(test_graph, EntityLookupQuery(operation="entity_lookup", entity_id="C"))
    duplicate = service.query(test_graph, EntityLookupQuery(operation="entity_lookup", tag="DUP"))
    wrong_case = service.query(test_graph, EntityLookupQuery(operation="entity_lookup", tag="exact"))

    assert by_id.entity_ids == ["C"]
    assert by_id.entities[0].assertion.review_status == "needs_source"
    assert duplicate.outcome == "ambiguous"
    assert duplicate.entity_ids == ["A", "B"]
    assert wrong_case.outcome == "not_found"
    assert service.query(test_graph, EntityLookupQuery(
        operation="entity_lookup", entity_id="missing"
    )).outcome == "not_found"


def test_empty_graph_returns_structured_outcomes() -> None:
    empty = graph(entity_ids=())
    assert GraphQueryService().query(empty, NeighborsQuery(
        operation="neighbors", entity_id="missing"
    )).outcome == "not_found"
    assert GraphQueryService().query(empty, EntityLookupQuery(
        operation="entity_lookup", tag="missing"
    )).outcome == "not_found"


def session_from_client() -> Generator[Session, None, None]:
    dependency = app.dependency_overrides[get_session]
    yield from dependency()


def persist_graph(client: TestClient, document_id: str) -> tuple[str, str]:
    del client
    generator = session_from_client()
    session = next(generator)
    try:
        suffix = document_id
        first = entity(f"entity-a-{suffix}", tag="EXACT", document_id=document_id)
        second = entity(f"entity-b-{suffix}", tag="OTHER", document_id=document_id)
        first.page_id = second.page_id = f"page-{document_id}"
        edge = connection(f"connection-a-{suffix}", first.id, second.id, document_id=document_id)
        session.add_all([entity_record(first), entity_record(second)])
        session.flush()
        session.add(connection_record(edge))
        session.commit()
        return first.id, second.id
    finally:
        generator.close()


def test_api_query_is_read_only_and_document_isolated(client: TestClient) -> None:
    first_document = client.post(
        "/documents", json={"name": "first.png", "sourceType": "image"}
    ).json()["id"]
    second_document = client.post(
        "/documents", json={"name": "second.png", "sourceType": "image"}
    ).json()["id"]
    source_id, target_id = persist_graph(client, first_document)
    persist_graph(client, second_document)
    before = client.get(f"/documents/{first_document}/graph").json()

    payload = {"operation": "shortest_path", "sourceEntityId": source_id, "targetEntityId": target_id}
    first_response = client.post(f"/documents/{first_document}/graph/query", json=payload)
    second_response = client.post(f"/documents/{first_document}/graph/query", json=payload)

    assert first_response.status_code == 200
    assert first_response.json() == second_response.json()
    assert first_response.json()["outcome"] == "ok"
    assert client.get(f"/documents/{first_document}/graph").json() == before
    assert client.post(f"/documents/{second_document}/graph/query", json={
        "operation": "entity_lookup", "entityId": source_id
    }).json()["outcome"] == "not_found"

    generator = session_from_client()
    session = next(generator)
    try:
        assert session.scalar(select(func.count()).select_from(GraphRevisionRecord)) == 0
    finally:
        generator.close()


def test_api_structured_errors_and_lookup_outcomes(client: TestClient) -> None:
    document_id = client.post(
        "/documents", json={"name": "query.png", "sourceType": "image"}
    ).json()["id"]
    persist_graph(client, document_id)

    lookup = client.post(f"/documents/{document_id}/graph/query", json={
        "operation": "entity_lookup", "tag": "EXACT"
    })
    assert lookup.status_code == 200
    assert lookup.json()["entityIds"] == [f"entity-a-{document_id}"]
    assert client.post(f"/documents/{document_id}/graph/query", json={
        "operation": "entity_lookup", "entityId": f"entity-a-{document_id}", "tag": "EXACT"
    }).status_code == 422
    assert client.post(f"/documents/{document_id}/graph/query", json={
        "operation": "unsupported", "entityId": "entity-a"
    }).status_code == 422
    assert client.post("/documents/missing/graph/query", json={
        "operation": "entity_lookup", "entityId": "entity-a"
    }).status_code == 404

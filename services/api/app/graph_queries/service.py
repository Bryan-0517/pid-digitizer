from __future__ import annotations

from collections import deque

from app.domain.models import EngineeringConnection, EngineeringGraph
from app.graph_queries.schemas import (
    AppliedFilters,
    ConnectionResult,
    DownstreamQuery,
    EntityLookupQuery,
    GraphQueryRequest,
    GraphQueryResult,
    NeighborsQuery,
    PathResult,
    ShortestPathQuery,
    UpstreamQuery,
)


ALL_CONNECTION_KINDS = ["ownership", "process", "reference", "signal", "unknown", "utility"]


class GraphQueryService:
    """Pure deterministic queries; this service never mutates the supplied graph."""

    def query(self, graph: EngineeringGraph, request: GraphQueryRequest) -> GraphQueryResult:
        if isinstance(request, EntityLookupQuery):
            return self._lookup(graph, request)
        kinds = sorted(set(
            ALL_CONNECTION_KINDS
            if request.connection_kinds is None
            else request.connection_kinds
        ))
        if isinstance(request, NeighborsQuery):
            return self._neighbors(graph, request.entity_id, kinds)
        if isinstance(request, UpstreamQuery):
            return self._traverse(graph, request.entity_id, kinds, upstream=True)
        if isinstance(request, DownstreamQuery):
            return self._traverse(graph, request.entity_id, kinds, upstream=False)
        return self._shortest_path(graph, request, kinds)

    def _lookup(self, graph: EngineeringGraph, request: EntityLookupQuery) -> GraphQueryResult:
        if request.entity_id is not None:
            matches = [entity for entity in graph.entities if entity.id == request.entity_id]
        else:
            matches = [entity for entity in graph.entities if entity.tag == request.tag]
        matches.sort(key=lambda entity: entity.id)
        outcome = "not_found" if not matches else "ambiguous" if len(matches) > 1 else "ok"
        return GraphQueryResult(
            operation="entity_lookup",
            outcome=outcome,
            entity_ids=[entity.id for entity in matches],
            entities=matches,
        )

    def _neighbors(
        self, graph: EngineeringGraph, entity_id: str, kinds: list[str]
    ) -> GraphQueryResult:
        if not self._has_entity(graph, entity_id):
            return self._missing("neighbors", kinds)
        incident = sorted(
            (
                connection
                for connection in graph.connections
                if connection.kind in kinds
                and entity_id in (connection.source_entity_id, connection.target_entity_id)
            ),
            key=lambda connection: connection.id,
        )
        neighbor_ids = sorted({
            connection.target_entity_id
            if connection.source_entity_id == entity_id
            else connection.source_entity_id
            for connection in incident
        })
        return GraphQueryResult(
            operation="neighbors",
            outcome="ok",
            entity_ids=neighbor_ids,
            connection_ids=[connection.id for connection in incident],
            connections=self._connection_results(incident),
            applied_filters=AppliedFilters(connection_kinds=kinds),
        )

    def _traverse(
        self, graph: EngineeringGraph, start: str, kinds: list[str], *, upstream: bool
    ) -> GraphQueryResult:
        operation = "upstream" if upstream else "downstream"
        if not self._has_entity(graph, start):
            return self._missing(operation, kinds)
        adjacency = self._adjacency(graph, kinds, mode="upstream" if upstream else "downstream")
        paths = self._breadth_first_paths(start, adjacency)
        ordered_ids = sorted(paths)
        path_results = [self._path_result(paths[entity_id]) for entity_id in ordered_ids]
        connection_ids = sorted({item for path in path_results for item in path.connection_ids})
        return GraphQueryResult(
            operation=operation,
            outcome="ok",
            entity_ids=ordered_ids,
            connection_ids=connection_ids,
            paths=path_results,
            connections=self._results_by_id(graph, connection_ids),
            applied_filters=AppliedFilters(connection_kinds=kinds),
        )

    def _shortest_path(
        self, graph: EngineeringGraph, request: ShortestPathQuery, kinds: list[str]
    ) -> GraphQueryResult:
        filters = AppliedFilters(connection_kinds=kinds, direction_mode=request.direction_mode)
        if not self._has_entity(graph, request.source_entity_id) or not self._has_entity(
            graph, request.target_entity_id
        ):
            return GraphQueryResult(
                operation="shortest_path", outcome="not_found", applied_filters=filters
            )
        adjacency = self._adjacency(graph, kinds, mode=request.direction_mode)
        paths = self._breadth_first_paths(request.source_entity_id, adjacency)
        if request.source_entity_id == request.target_entity_id:
            path = [(request.source_entity_id, None)]
        else:
            path = paths.get(request.target_entity_id)
        if path is None:
            return GraphQueryResult(
                operation="shortest_path", outcome="no_path", applied_filters=filters
            )
        result = self._path_result(path)
        return GraphQueryResult(
            operation="shortest_path",
            outcome="ok",
            entity_ids=result.entity_ids,
            connection_ids=result.connection_ids,
            paths=[result],
            connections=self._results_by_id(graph, result.connection_ids),
            applied_filters=filters,
        )

    def _adjacency(
        self, graph: EngineeringGraph, kinds: list[str], *, mode: str
    ) -> dict[str, list[tuple[str, str]]]:
        adjacency: dict[str, list[tuple[str, str]]] = {entity.id: [] for entity in graph.entities}
        for connection in graph.connections:
            if connection.kind not in kinds:
                continue
            source, target = self._effective_endpoints(connection)
            if mode == "undirected":
                source, target = connection.source_entity_id, connection.target_entity_id
                adjacency[source].append((target, connection.id))
                adjacency[target].append((source, connection.id))
            elif source is not None and target is not None:
                if mode == "upstream":
                    source, target = target, source
                adjacency[source].append((target, connection.id))
        for edges in adjacency.values():
            edges.sort(key=lambda edge: (edge[0], edge[1]))
        return adjacency

    @staticmethod
    def _effective_endpoints(connection: EngineeringConnection) -> tuple[str | None, str | None]:
        if connection.direction == "source_to_target":
            return connection.source_entity_id, connection.target_entity_id
        if connection.direction == "target_to_source":
            return connection.target_entity_id, connection.source_entity_id
        return None, None

    @staticmethod
    def _breadth_first_paths(
        start: str, adjacency: dict[str, list[tuple[str, str]]]
    ) -> dict[str, list[tuple[str, str | None]]]:
        paths: dict[str, list[tuple[str, str | None]]] = {start: [(start, None)]}
        queue: deque[str] = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor, connection_id in adjacency[current]:
                if neighbor in paths:
                    continue
                paths[neighbor] = [*paths[current], (neighbor, connection_id)]
                queue.append(neighbor)
        paths.pop(start)
        return paths

    @staticmethod
    def _path_result(path: list[tuple[str, str | None]]) -> PathResult:
        return PathResult(
            entity_ids=[entity_id for entity_id, _ in path],
            connection_ids=[connection_id for _, connection_id in path if connection_id is not None],
        )

    @staticmethod
    def _connection_results(connections: list[EngineeringConnection]) -> list[ConnectionResult]:
        return [
            ConnectionResult(
                id=connection.id,
                source_entity_id=connection.source_entity_id,
                target_entity_id=connection.target_entity_id,
                kind=connection.kind,
                direction=connection.direction,
                assertion=connection.assertion,
                provenance=connection.provenance,
                confidence=connection.confidence,
            )
            for connection in connections
        ]

    def _results_by_id(self, graph: EngineeringGraph, ids: list[str]) -> list[ConnectionResult]:
        wanted = set(ids)
        return self._connection_results(sorted(
            (connection for connection in graph.connections if connection.id in wanted),
            key=lambda connection: connection.id,
        ))

    @staticmethod
    def _has_entity(graph: EngineeringGraph, entity_id: str) -> bool:
        return any(entity.id == entity_id for entity in graph.entities)

    @staticmethod
    def _missing(operation: str, kinds: list[str]) -> GraphQueryResult:
        return GraphQueryResult(
            operation=operation, outcome="not_found",
            applied_filters=AppliedFilters(connection_kinds=kinds),
        )

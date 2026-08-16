from __future__ import annotations

from app.chat.intent import ParsedIntent, resolve_intent
from app.chat.schemas import (
    ChatRequest,
    ChatResponse,
    ChatWarning,
    HighlightRequest,
    ResolvedIntent,
    VerbalizationMetadata,
)
from app.chat.verbalizer import TextVerbalizer, VerbalizationInput
from app.domain.models import EngineeringEntity, EngineeringGraph
from app.graph_queries.schemas import (
    DownstreamQuery,
    EntityLookupQuery,
    GraphQueryResult,
    NeighborsQuery,
    ShortestPathQuery,
    UpstreamQuery,
)
from app.graph_queries.service import GraphQueryService


class ChatService:
    def __init__(
        self,
        query_service: GraphQueryService | None = None,
        verbalizer: TextVerbalizer | None = None,
    ):
        self.query_service = query_service or GraphQueryService()
        self.verbalizer = verbalizer

    async def respond(self, graph: EngineeringGraph, request: ChatRequest) -> ChatResponse:
        parsed = resolve_intent(request.message)
        if parsed is None:
            return ChatResponse(
                outcome="unsupported",
                answer="This request is outside the supported graph-query patterns.",
            )

        query_results: list[GraphQueryResult] = []
        resolved_ids: list[str] = []
        for reference in parsed.references:
            resolution, results = self._resolve_entity(graph, reference)
            query_results.extend(results)
            if len(resolution) > 1:
                candidate_ids = sorted(resolution)
                return ChatResponse(
                    outcome="clarification_required",
                    resolved_intent=ResolvedIntent(
                        operation=parsed.operation,
                        references=list(parsed.references),
                        resolved_entity_ids=candidate_ids,
                    ),
                    query_results=query_results,
                    answer="The reference matches multiple canonical entities. Clarification is required.",
                    supporting_entity_ids=candidate_ids,
                    highlight=HighlightRequest(entity_ids=candidate_ids),
                    warnings=self._warnings(query_results),
                )
            if not resolution:
                return ChatResponse(
                    outcome="not_found",
                    resolved_intent=ResolvedIntent(
                        operation=parsed.operation, references=list(parsed.references)
                    ),
                    query_results=query_results,
                    answer=f"The graph does not contain an entity matching '{reference}'.",
                )
            resolved_ids.append(resolution[0])

        intent = ResolvedIntent(
            operation=parsed.operation,
            references=list(parsed.references),
            resolved_entity_ids=resolved_ids,
        )
        primary = self._execute(graph, parsed, resolved_ids)
        query_results.append(primary)
        if primary.outcome == "no_path":
            return ChatResponse(
                outcome="no_path",
                resolved_intent=intent,
                query_results=query_results,
                answer=(
                    "The canonical graph does not establish a path between the requested "
                    "entities under the selected traversal rules."
                ),
                supporting_entity_ids=sorted(set(resolved_ids)),
                highlight=HighlightRequest(entity_ids=sorted(set(resolved_ids))),
                warnings=self._warnings(query_results),
            )

        result_ids = sorted(set(primary.entity_ids) | set(resolved_ids))
        already_loaded = {
            entity.id for result in query_results for entity in result.entities
        }
        for entity_id in result_ids:
            if entity_id not in already_loaded:
                query_results.append(self.query_service.query(
                    graph,
                    EntityLookupQuery(operation="entity_lookup", entity_id=entity_id),
                ))

        connection_ids = sorted(primary.connection_ids)
        warnings = self._warnings(query_results)
        answer = self._answer(parsed, query_results, primary, resolved_ids)
        response = ChatResponse(
            outcome="ok",
            resolved_intent=intent,
            query_results=query_results,
            answer=answer,
            supporting_entity_ids=result_ids,
            supporting_connection_ids=connection_ids,
            highlight=HighlightRequest(
                entity_ids=result_ids, connection_ids=connection_ids
            ),
            warnings=warnings,
        )
        if request.verbalize and self.verbalizer is not None:
            try:
                verbalized = await self.verbalizer.verbalize(VerbalizationInput(
                    deterministic_answer=answer,
                    query_results=tuple(query_results),
                    supporting_entity_ids=tuple(result_ids),
                    supporting_connection_ids=tuple(connection_ids),
                    warnings=tuple(warnings),
                ))
                response.answer = verbalized.text
                response.verbalization_metadata = VerbalizationMetadata(
                    provider=verbalized.provider, model=verbalized.model
                )
            except Exception:
                response.warnings.append(ChatWarning(
                    code="verbalization_failed",
                    message="Optional verbalization failed; the deterministic answer was retained.",
                ))
        return response

    def _resolve_entity(
        self, graph: EngineeringGraph, reference: str
    ) -> tuple[list[str], list[GraphQueryResult]]:
        by_tag = self.query_service.query(
            graph, EntityLookupQuery(operation="entity_lookup", tag=reference)
        )
        by_id = self.query_service.query(
            graph, EntityLookupQuery(operation="entity_lookup", entity_id=reference)
        )
        matches = sorted(set(by_tag.entity_ids) | set(by_id.entity_ids))
        return matches, [by_tag, by_id]

    def _execute(
        self, graph: EngineeringGraph, parsed: ParsedIntent, ids: list[str]
    ) -> GraphQueryResult:
        if parsed.operation == "neighbors":
            query = NeighborsQuery(operation="neighbors", entity_id=ids[0])
        elif parsed.operation == "upstream":
            query = UpstreamQuery(operation="upstream", entity_id=ids[0])
        elif parsed.operation == "downstream":
            query = DownstreamQuery(operation="downstream", entity_id=ids[0])
        elif parsed.operation == "shortest_path":
            query = ShortestPathQuery(
                operation="shortest_path",
                source_entity_id=ids[0],
                target_entity_id=ids[1],
            )
        else:
            query = EntityLookupQuery(operation="entity_lookup", entity_id=ids[0])
        return self.query_service.query(graph, query)

    @staticmethod
    def _answer(
        parsed: ParsedIntent,
        results: list[GraphQueryResult],
        primary: GraphQueryResult,
        resolved_ids: list[str],
    ) -> str:
        entities = {
            entity.id: entity for result in results for entity in result.entities
        }
        labels = [ChatService._label(entities[entity_id]) for entity_id in resolved_ids]
        if parsed.operation == "neighbors":
            return f"{labels[0]} has {len(primary.entity_ids)} directly connected canonical entities."
        if parsed.operation == "upstream":
            return f"The graph establishes {len(primary.entity_ids)} upstream entities from {labels[0]}."
        if parsed.operation == "downstream":
            return f"The graph establishes {len(primary.entity_ids)} downstream entities from {labels[0]}."
        if parsed.operation == "shortest_path":
            path = primary.paths[0]
            return (
                f"A directed path from {labels[0]} to {labels[1]} contains "
                f"{len(path.entity_ids)} entities and {len(path.connection_ids)} connections."
            )
        return f"{labels[0]} resolves to canonical entity {resolved_ids[0]}."

    @staticmethod
    def _label(entity: EngineeringEntity) -> str:
        return entity.tag or entity.display_name or entity.id

    @staticmethod
    def _warnings(results: list[GraphQueryResult]) -> list[ChatWarning]:
        entities = {
            entity.id: entity for result in results for entity in result.entities
        }
        connections = {
            connection.id: connection
            for result in results
            for connection in result.connections
        }
        warnings: list[ChatWarning] = []
        for entity_id in sorted(entities):
            entity = entities[entity_id]
            if entity.assertion.mode == "inferred" or entity.assertion.review_status not in {
                "confirmed", "corrected"
            }:
                warnings.append(ChatWarning(
                    code="uncertain_entity",
                    message=f"Canonical entity {entity.id} is not verified.",
                    object_type="entity",
                    object_id=entity.id,
                    assertion=entity.assertion,
                    confidence=entity.confidence,
                    provenance=entity.provenance,
                ))
        for connection_id in sorted(connections):
            connection = connections[connection_id]
            if connection.assertion.mode == "inferred" or connection.assertion.review_status not in {
                "confirmed", "corrected"
            }:
                warnings.append(ChatWarning(
                    code="uncertain_connection",
                    message=f"Canonical connection {connection.id} is not verified.",
                    object_type="connection",
                    object_id=connection.id,
                    assertion=connection.assertion,
                    confidence=connection.confidence,
                    provenance=connection.provenance,
                    connection_kind=connection.kind,
                    original_direction=connection.direction,
                ))
        return warnings

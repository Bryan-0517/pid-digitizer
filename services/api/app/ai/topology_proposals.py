import json
from typing import Literal

from pydantic import Field

from app.ai.contracts import AIContract, PageImageInput, StructuredExtractionRequest
from app.ai.entity_proposals import CandidateProperty, CandidateProvenance, EntityCandidate
from app.domain.models import JsonValue


class TopologyAssertion(AIContract):
    mode: Literal["inferred"]
    review_status: Literal["unreviewed", "needs_source"]


class ConnectionCandidate(AIContract):
    candidate_id: str
    source_entity_id: str
    target_entity_id: str
    kind: Literal["process", "utility", "signal", "ownership", "reference", "unknown"]
    medium: str | None = None
    direction: Literal[
        "source_to_target", "target_to_source", "undirected", "unknown"
    ] = "unknown"
    properties: list[CandidateProperty] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    assertion: TopologyAssertion
    provenance: list[CandidateProvenance] = Field(min_length=1)


class TopologyExtractionProposal(AIContract):
    connections: list[ConnectionCandidate]
    warnings: list[str] = Field(default_factory=list)


def build_topology_extraction_request(
    *,
    request_id: str,
    image: PageImageInput,
    entities: list[EntityCandidate],
    provider_options: dict[str, JsonValue] | None = None,
) -> StructuredExtractionRequest:
    entity_context = [
        {
            "candidateId": entity.candidate_id,
            "kind": entity.kind,
            "tag": entity.tag,
            "displayName": entity.display_name,
        }
        for entity in entities
    ]
    return StructuredExtractionRequest.for_output(
        request_id=request_id,
        image=image,
        system_instruction=(
            "Propose only visible topology between the supplied entity candidates. Every source "
            "and target ID must exactly match a supplied candidate ID. Mark every relationship "
            "assertion mode as inferred. Do not fabricate geometry or missing relationships. "
            "Retain ambiguity as warnings and use needs_source when evidence is insufficient."
        ),
        task_prompt=(
            "Inspect the same page image for process, utility, signal, ownership, reference, or "
            "unknown relationships between these candidates:\n"
            + json.dumps(entity_context, ensure_ascii=False, separators=(",", ":"))
        ),
        output_type=TopologyExtractionProposal,
        provider_options=provider_options,
    )


def validate_topology_references(
    proposal: TopologyExtractionProposal, entities: list[EntityCandidate]
) -> None:
    entity_ids = {entity.candidate_id for entity in entities}
    broken = [
        connection.candidate_id
        for connection in proposal.connections
        if connection.source_entity_id not in entity_ids
        or connection.target_entity_id not in entity_ids
    ]
    if broken:
        raise ValueError("topology proposal references unknown entity candidates: " + ", ".join(broken))

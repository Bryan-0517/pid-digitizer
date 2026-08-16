from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from app.domain.models import Assertion, DomainModel, EvidenceRef
from app.graph_queries.schemas import GraphQueryResult


ChatOutcome = Literal[
    "ok", "not_found", "clarification_required", "unsupported", "no_path"
]
ChatIntentName = Literal[
    "neighbors", "upstream", "downstream", "shortest_path", "entity_lookup"
]


class ChatRequest(DomainModel):
    message: str = Field(min_length=1, max_length=500)
    verbalize: bool = False

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be blank")
        return value


class ResolvedIntent(DomainModel):
    operation: ChatIntentName
    references: list[str]
    resolved_entity_ids: list[str] = Field(default_factory=list)


class HighlightRequest(DomainModel):
    entity_ids: list[str] = Field(default_factory=list)
    connection_ids: list[str] = Field(default_factory=list)


class ChatWarning(DomainModel):
    code: Literal["uncertain_entity", "uncertain_connection", "verbalization_failed"]
    message: str
    object_type: Literal["entity", "connection"] | None = None
    object_id: str | None = None
    assertion: Assertion | None = None
    confidence: float | None = None
    provenance: list[EvidenceRef] = Field(default_factory=list)
    connection_kind: str | None = None
    original_direction: str | None = None


class VerbalizationMetadata(DomainModel):
    provider: str
    model: str


class ChatResponse(DomainModel):
    outcome: ChatOutcome
    resolved_intent: ResolvedIntent | None = None
    query_results: list[GraphQueryResult] = Field(default_factory=list)
    answer: str
    supporting_entity_ids: list[str] = Field(default_factory=list)
    supporting_connection_ids: list[str] = Field(default_factory=list)
    highlight: HighlightRequest = Field(default_factory=HighlightRequest)
    warnings: list[ChatWarning] = Field(default_factory=list)
    verbalization_metadata: VerbalizationMetadata | None = None

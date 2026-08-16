from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.chat.schemas import ChatWarning
from app.graph_queries.schemas import GraphQueryResult


@dataclass(frozen=True)
class VerbalizationInput:
    deterministic_answer: str
    query_results: tuple[GraphQueryResult, ...]
    supporting_entity_ids: tuple[str, ...]
    supporting_connection_ids: tuple[str, ...]
    warnings: tuple[ChatWarning, ...]


@dataclass(frozen=True)
class VerbalizationOutput:
    text: str
    provider: str
    model: str


class TextVerbalizer(Protocol):
    async def verbalize(self, request: VerbalizationInput) -> VerbalizationOutput: ...


class DeterministicMockVerbalizer:
    """Test-only verbalizer that cannot add graph content."""

    async def verbalize(self, request: VerbalizationInput) -> VerbalizationOutput:
        return VerbalizationOutput(
            text=f"Grounded summary: {request.deterministic_answer}",
            provider="mock",
            model="deterministic-verbalizer-v1",
        )

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.ai.contracts import ProviderMetadata, StructuredExtractionRequest, StructuredExtractionResponse, TokenUsage
from app.ai.errors import MalformedStructuredOutputError, ProviderRequestError, ResponseParsingError

OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass(frozen=True)
class MockFixture:
    output: Any = None
    scenario: str = "success"
    model: str = "mock-structured-v1"
    input_tokens: int | None = 10
    output_tokens: int | None = 5
    warnings: tuple[str, ...] = ()


class MockAIProvider:
    provider_name = "mock"

    def __init__(self, fixtures: dict[str, MockFixture]):
        self.fixtures = fixtures

    async def extract(
        self, request: StructuredExtractionRequest, output_type: type[OutputT]
    ) -> StructuredExtractionResponse[OutputT]:
        fixture = self.fixtures.get(request.request_id)
        if fixture is None:
            raise ProviderRequestError()
        if fixture.scenario == "failure":
            raise ProviderRequestError()
        if fixture.scenario == "parsing_failure":
            raise ResponseParsingError()
        try:
            parsed = output_type.model_validate(fixture.output)
        except (ValidationError, TypeError, ValueError) as exc:
            raise MalformedStructuredOutputError() from exc
        total = None
        if fixture.input_tokens is not None and fixture.output_tokens is not None:
            total = fixture.input_tokens + fixture.output_tokens
        return StructuredExtractionResponse[OutputT](
            parsed_output=parsed,
            metadata=ProviderMetadata(
                provider=self.provider_name, model=fixture.model,
                request_id=request.request_id, latency_ms=0,
                usage=TokenUsage(
                    input_tokens=fixture.input_tokens, output_tokens=fixture.output_tokens,
                    total_tokens=total,
                ),
                warnings=list(fixture.warnings),
                raw_response_ref=f"mock-fixture:{request.request_id}",
                debug_metadata={"fixtureDriven": True},
            ),
        )

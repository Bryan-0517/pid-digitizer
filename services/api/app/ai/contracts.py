from __future__ import annotations

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.models import JsonValue


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class AIContract(BaseModel):
    model_config = ConfigDict(extra="forbid", alias_generator=lambda value: _camel(value), populate_by_name=True)


class PageImageInput(AIContract):
    source_ref: str
    media_type: str
    content: bytes | None = Field(default=None, repr=False)
    uri: str | None = None
    width_px: int | None = Field(default=None, gt=0)
    height_px: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_input(self) -> "PageImageInput":
        if self.media_type not in {"image/png", "image/jpeg"}:
            raise ValueError("unsupported media input; expected image/png or image/jpeg")
        if (self.content is None) == (self.uri is None):
            raise ValueError("exactly one of content or uri is required")
        return self


class StructuredExtractionRequest(AIContract):
    request_id: str
    image: PageImageInput
    system_instruction: str
    task_prompt: str
    output_schema: dict[str, Any]
    provider_options: dict[str, JsonValue] = Field(default_factory=dict)

    @classmethod
    def for_output(
        cls, *, request_id: str, image: PageImageInput, system_instruction: str,
        task_prompt: str, output_type: type[BaseModel],
        provider_options: dict[str, JsonValue] | None = None,
    ) -> "StructuredExtractionRequest":
        return cls(
            request_id=request_id, image=image, system_instruction=system_instruction,
            task_prompt=task_prompt, output_schema=output_type.model_json_schema(),
            provider_options=provider_options or {},
        )


class TokenUsage(AIContract):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class ProviderMetadata(AIContract):
    provider: str
    model: str
    request_id: str
    latency_ms: float = Field(ge=0)
    usage: TokenUsage | None = None
    warnings: list[str] = Field(default_factory=list)
    raw_response_ref: str | None = None
    debug_metadata: dict[str, JsonValue] = Field(default_factory=dict)


ProviderFailureCategory = Literal[
    "incomplete_output",
    "max_output_tokens_exhausted",
    "malformed_structured_json",
    "structured_output_schema_validation",
    "provider_api_failure",
    "timeout",
]


class ProviderFailureMetadata(AIContract):
    provider: str
    model: str | None = None
    request_id: str
    response_id: str | None = None
    http_status: int | None = None
    response_status: str | None = None
    incomplete_details: dict[str, JsonValue] | None = None
    termination_reason: str | None = None
    usage: TokenUsage | None = None
    latency_ms: float | None = Field(default=None, ge=0)
    failure_category: ProviderFailureCategory
    structured_parsing_began: bool
    candidate_validation_began: bool


OutputT = TypeVar("OutputT", bound=BaseModel)


class StructuredExtractionResponse(AIContract, Generic[OutputT]):
    parsed_output: OutputT
    metadata: ProviderMetadata

from __future__ import annotations

import base64
from time import perf_counter
from typing import Any, TypeVar

from openai import APIError, APITimeoutError, AsyncOpenAI, AuthenticationError
from pydantic import BaseModel, ValidationError

from app.ai.contracts import (
    ProviderMetadata,
    StructuredExtractionRequest,
    StructuredExtractionResponse,
    TokenUsage,
)
from app.ai.errors import (
    MalformedStructuredOutputError,
    ProviderConfigurationError,
    ProviderRequestError,
    ProviderTimeoutError,
    ResponseParsingError,
)

OutputT = TypeVar("OutputT", bound=BaseModel)
_ALLOWED_OPTIONS = {"max_output_tokens", "temperature", "reasoning"}


class OpenAIProvider:
    provider_name = "openai"

    def __init__(self, *, api_key: str, model: str, client: Any | None = None):
        if not api_key or not model:
            raise ProviderConfigurationError("OpenAI provider requires AI_MODEL and AI_API_KEY")
        self.model = model
        self.client = client or AsyncOpenAI(api_key=api_key)

    async def extract(
        self, request: StructuredExtractionRequest, output_type: type[OutputT]
    ) -> StructuredExtractionResponse[OutputT]:
        started = perf_counter()
        image_url = request.image.uri or _data_url(
            request.image.media_type, request.image.content or b""
        )
        image_content: dict[str, Any] = {"type": "input_image", "image_url": image_url}
        detail = request.provider_options.get("image_detail")
        if detail in {"auto", "low", "high"}:
            image_content["detail"] = detail
        options = {
            key: value
            for key, value in request.provider_options.items()
            if key in _ALLOWED_OPTIONS
        }
        try:
            response = await self.client.responses.parse(
                model=self.model,
                instructions=request.system_instruction,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": request.task_prompt},
                            image_content,
                        ],
                    }
                ],
                text_format=output_type,
                **options,
            )
        except AuthenticationError as exc:
            raise ProviderConfigurationError("OpenAI authentication failed") from exc
        except APITimeoutError as exc:
            raise ProviderTimeoutError() from exc
        except APIError as exc:
            raise ProviderRequestError() from exc
        except (ValidationError, ValueError) as exc:
            raise MalformedStructuredOutputError() from exc
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            status = getattr(response, "status", None) or "unknown"
            incomplete = getattr(response, "incomplete_details", None)
            incomplete_reason = getattr(incomplete, "reason", None)
            reason = f"status={status}"
            if incomplete_reason:
                reason += f", incompleteReason={incomplete_reason}"
            raise ResponseParsingError(reason)
        try:
            validated = output_type.model_validate(parsed)
        except (ValidationError, TypeError, ValueError) as exc:
            raise MalformedStructuredOutputError() from exc
        usage = getattr(response, "usage", None)
        warnings = []
        status = getattr(response, "status", None)
        if status and status != "completed":
            warnings.append(f"OpenAI response status: {status}")
        return StructuredExtractionResponse[OutputT](
            parsed_output=validated,
            metadata=ProviderMetadata(
                provider=self.provider_name,
                model=getattr(response, "model", None) or self.model,
                request_id=request.request_id,
                latency_ms=(perf_counter() - started) * 1000,
                usage=(
                    TokenUsage(
                        input_tokens=getattr(usage, "input_tokens", None),
                        output_tokens=getattr(usage, "output_tokens", None),
                        total_tokens=getattr(usage, "total_tokens", None),
                    )
                    if usage is not None
                    else None
                ),
                warnings=warnings,
                raw_response_ref=getattr(response, "id", None),
                debug_metadata={"responseStatus": status or "unknown"},
            ),
        )


def _data_url(media_type: str, content: bytes) -> str:
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{media_type};base64,{encoded}"

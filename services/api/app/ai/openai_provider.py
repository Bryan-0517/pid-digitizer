from __future__ import annotations

import base64
import json
from time import perf_counter
from typing import Any, TypeVar

from openai import APIError, APITimeoutError, AsyncOpenAI, AuthenticationError
from pydantic import BaseModel, ValidationError

from app.ai.contracts import (
    ProviderMetadata,
    ProviderFailureMetadata,
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
        request_arguments = {
            "model": self.model,
            "instructions": request.system_instruction,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": request.task_prompt},
                        image_content,
                    ],
                }
            ],
            "text_format": output_type,
            **options,
        }
        raw_response = None
        safe_payload: dict[str, Any] = {}
        try:
            raw_response = await self.client.responses.with_raw_response.parse(
                **request_arguments
            )
            payload = await raw_response.json()
            safe_payload = payload if isinstance(payload, dict) else {}
            failure = _preparse_failure_metadata(
                raw_response=raw_response,
                payload=safe_payload,
                request_id=request.request_id,
                configured_model=self.model,
                latency_ms=(perf_counter() - started) * 1000,
            )
            if failure is not None:
                raise ResponseParsingError(
                    failure.termination_reason or failure.response_status,
                    failure_metadata=failure,
                )
            response = await raw_response.parse()
        except AuthenticationError as exc:
            error = ProviderConfigurationError("OpenAI authentication failed")
            error.failure_metadata = _transport_failure_metadata(
                request_id=request.request_id,
                model=self.model,
                started=started,
                category="provider_api_failure",
                error=exc,
            )
            raise error from exc
        except APITimeoutError as exc:
            raise ProviderTimeoutError(
                _transport_failure_metadata(
                    request_id=request.request_id,
                    model=self.model,
                    started=started,
                    category="timeout",
                    error=exc,
                )
            ) from exc
        except APIError as exc:
            raise ProviderRequestError(
                _transport_failure_metadata(
                    request_id=request.request_id,
                    model=self.model,
                    started=started,
                    category="provider_api_failure",
                    error=exc,
                )
            ) from exc
        except ValidationError as exc:
            category, candidate_validation_began = _validation_failure_class(safe_payload)
            raise MalformedStructuredOutputError(
                _safe_failure_metadata(
                    raw_response=raw_response,
                    payload=safe_payload,
                    request_id=request.request_id,
                    configured_model=self.model,
                    latency_ms=(perf_counter() - started) * 1000,
                    category=category,
                    structured_parsing_began=True,
                    candidate_validation_began=candidate_validation_began,
                )
            ) from exc
        except ValueError as exc:
            raise MalformedStructuredOutputError(
                _safe_failure_metadata(
                    raw_response=raw_response,
                    payload=safe_payload,
                    request_id=request.request_id,
                    configured_model=self.model,
                    latency_ms=(perf_counter() - started) * 1000,
                    category="malformed_structured_json",
                    structured_parsing_began=True,
                    candidate_validation_began=False,
                )
            ) from exc
        parsed = getattr(response, "output_parsed", None)
        if parsed is None:
            status = getattr(response, "status", None) or "unknown"
            incomplete = getattr(response, "incomplete_details", None)
            incomplete_reason = getattr(incomplete, "reason", None)
            reason = f"status={status}"
            if incomplete_reason:
                reason += f", incompleteReason={incomplete_reason}"
            raise ResponseParsingError(
                reason,
                failure_metadata=_safe_failure_metadata(
                    raw_response=raw_response,
                    payload=safe_payload,
                    request_id=request.request_id,
                    configured_model=self.model,
                    latency_ms=(perf_counter() - started) * 1000,
                    category="structured_output_schema_validation",
                    structured_parsing_began=True,
                    candidate_validation_began=False,
                ),
            )
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


def _preparse_failure_metadata(
    *,
    raw_response: Any,
    payload: dict[str, Any],
    request_id: str,
    configured_model: str,
    latency_ms: float,
) -> ProviderFailureMetadata | None:
    status = payload.get("status")
    if status == "completed" or status is None:
        return None
    incomplete = payload.get("incomplete_details")
    reason = incomplete.get("reason") if isinstance(incomplete, dict) else None
    category = (
        "max_output_tokens_exhausted"
        if reason == "max_output_tokens"
        else "incomplete_output"
        if status == "incomplete"
        else "provider_api_failure"
    )
    return _safe_failure_metadata(
        raw_response=raw_response,
        payload=payload,
        request_id=request_id,
        configured_model=configured_model,
        latency_ms=latency_ms,
        category=category,
        structured_parsing_began=False,
        candidate_validation_began=False,
    )


def _safe_failure_metadata(
    *,
    raw_response: Any,
    payload: dict[str, Any],
    request_id: str,
    configured_model: str,
    latency_ms: float,
    category: str,
    structured_parsing_began: bool,
    candidate_validation_began: bool,
) -> ProviderFailureMetadata:
    incomplete = payload.get("incomplete_details")
    reason = incomplete.get("reason") if isinstance(incomplete, dict) else None
    usage = payload.get("usage")
    return ProviderFailureMetadata(
        provider="openai",
        model=payload.get("model") if isinstance(payload.get("model"), str) else configured_model,
        request_id=request_id,
        response_id=payload.get("id") if isinstance(payload.get("id"), str) else None,
        http_status=getattr(getattr(raw_response, "http_response", None), "status_code", None),
        response_status=payload.get("status") if isinstance(payload.get("status"), str) else None,
        incomplete_details={"reason": reason} if isinstance(reason, str) else None,
        termination_reason=reason if isinstance(reason, str) else None,
        usage=TokenUsage(
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            total_tokens=usage.get("total_tokens"),
        )
        if isinstance(usage, dict)
        else None,
        latency_ms=latency_ms,
        failure_category=category,
        structured_parsing_began=structured_parsing_began,
        candidate_validation_began=candidate_validation_began,
    )


def _validation_failure_class(payload: dict[str, Any]) -> tuple[str, bool]:
    text = _first_output_text(payload)
    if text is None:
        return "structured_output_schema_validation", False
    try:
        decoded = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return "malformed_structured_json", False
    candidate_validation_began = isinstance(decoded, dict) and isinstance(
        decoded.get("candidates"), list
    )
    return "structured_output_schema_validation", candidate_validation_began


def _first_output_text(payload: dict[str, Any]) -> str | None:
    for output in payload.get("output", []):
        if not isinstance(output, dict) or output.get("type") != "message":
            continue
        for content in output.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = content.get("text")
                return text if isinstance(text, str) else None
    return None


def _transport_failure_metadata(
    *, request_id: str, model: str, started: float, category: str, error: Exception
) -> ProviderFailureMetadata:
    return ProviderFailureMetadata(
        provider="openai",
        model=model,
        request_id=request_id,
        response_id=getattr(error, "request_id", None),
        http_status=getattr(error, "status_code", None),
        latency_ms=(perf_counter() - started) * 1000,
        failure_category=category,
        structured_parsing_began=False,
        candidate_validation_began=False,
    )

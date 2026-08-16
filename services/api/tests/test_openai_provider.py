import asyncio
from pathlib import Path
from types import SimpleNamespace

import httpx
from openai import APIConnectionError, APITimeoutError
from pydantic import ValidationError
import pytest

from app.ai.contracts import AIContract, PageImageInput
from app.ai.entity_proposals import (
    EntityExtractionProposal,
    build_entity_extraction_request,
    page_image_from_path,
    proposal_validation_diagnostics,
)
from app.ai.errors import (
    MalformedStructuredOutputError,
    ProviderRequestError,
    ProviderTimeoutError,
    ResponseParsingError,
)
from app.ai.factory import create_ai_provider
from app.ai.openai_provider import OpenAIProvider
from app.config import Settings


class FakeRawResponse:
    def __init__(self, response: object, payload: dict[str, object], parse_error: Exception | None):
        self.response = response
        self.payload = payload
        self.parse_error = parse_error
        self.http_response = SimpleNamespace(status_code=200)

    async def json(self):
        return self.payload

    async def parse(self):
        if self.parse_error is not None:
            raise self.parse_error
        return self.response


class FakeResponses:
    def __init__(
        self,
        response: object,
        *,
        payload: dict[str, object] | None = None,
        parse_error: Exception | None = None,
        request_error: Exception | None = None,
    ):
        self.response = response
        self.payload = payload or _safe_payload(response)
        self.parse_error = parse_error
        self.request_error = request_error
        self.calls: list[dict[str, object]] = []

    @property
    def with_raw_response(self):
        return self

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.request_error is not None:
            raise self.request_error
        return FakeRawResponse(self.response, self.payload, self.parse_error)


class FakeClient:
    def __init__(self, response: object, **kwargs):
        self.responses = FakeResponses(response, **kwargs)


def proposal() -> EntityExtractionProposal:
    return EntityExtractionProposal.model_validate(
        {
            "candidates": [
                {
                    "candidateId": "candidate-1",
                    "kind": "instrument",
                    "tag": "TE-0807A",
                    "properties": [
                        {"name": "variable", "value": "temperature", "evidenceText": "TEMP"}
                    ],
                    "confidence": 0.8,
                    "provenance": [{"sourceRef": "IMG_6807.JPG", "evidenceText": "TE-0807A"}],
                }
            ],
            "warnings": [],
        }
    )


def response(parsed_output: object) -> object:
    return SimpleNamespace(
        id="resp_fixture",
        model="configured-model",
        status="completed",
        output_parsed=parsed_output,
        usage=SimpleNamespace(input_tokens=100, output_tokens=20, total_tokens=120),
    )


def _safe_payload(value: object) -> dict[str, object]:
    usage = getattr(value, "usage", None)
    return {
        "id": getattr(value, "id", None),
        "model": getattr(value, "model", None),
        "status": getattr(value, "status", None),
        "incomplete_details": getattr(value, "incomplete_details", None),
        "usage": {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        },
        "output": [],
    }


def test_openai_provider_sends_image_and_returns_validated_proposal() -> None:
    client = FakeClient(response(proposal()))
    provider = OpenAIProvider(api_key="test-only", model="configured-model", client=client)
    request = build_entity_extraction_request(
        request_id="extract-1",
        image=PageImageInput(
            sourceRef="IMG_6807.JPG", mediaType="image/jpeg", content=b"jpeg"
        ),
        provider_options={"image_detail": "high", "max_output_tokens": 1000},
    )

    result = asyncio.run(provider.extract(request, EntityExtractionProposal))

    call = client.responses.calls[0]
    assert call["model"] == "configured-model"
    assert call["text_format"] is EntityExtractionProposal
    assert call["instructions"] == request.system_instruction
    content = call["input"][0]["content"]
    assert content[0] == {"type": "input_text", "text": request.task_prompt}
    assert content[1] == {
        "type": "input_image",
        "image_url": "data:image/jpeg;base64,anBlZw==",
        "detail": "high",
    }
    assert call["max_output_tokens"] == 1000
    assert result.parsed_output == proposal()
    assert result.metadata.provider == "openai"
    assert result.metadata.model == "configured-model"
    assert result.metadata.usage.total_tokens == 120
    assert result.metadata.raw_response_ref == "resp_fixture"


def test_openai_provider_accepts_page_image_uri_without_loading_it() -> None:
    client = FakeClient(response(proposal()))
    provider = OpenAIProvider(api_key="test-only", model="configured-model", client=client)
    request = build_entity_extraction_request(
        request_id="extract-uri",
        image=PageImageInput(
            sourceRef="document-page:1",
            mediaType="image/png",
            uri="https://example.invalid/page.png",
        ),
    )

    asyncio.run(provider.extract(request, EntityExtractionProposal))

    image = client.responses.calls[0]["input"][0]["content"][1]
    assert image["image_url"] == "https://example.invalid/page.png"


def test_openai_provider_rejects_missing_structured_output() -> None:
    client = FakeClient(response(None))
    provider = OpenAIProvider(api_key="test-only", model="configured-model", client=client)
    request = build_entity_extraction_request(
        request_id="extract-invalid",
        image=PageImageInput(sourceRef="page", mediaType="image/png", content=b"png"),
    )

    with pytest.raises(ResponseParsingError):
        asyncio.run(provider.extract(request, EntityExtractionProposal))


@pytest.mark.parametrize(
    ("reason", "category"),
    [
        ("content_filter", "incomplete_output"),
        ("max_output_tokens", "max_output_tokens_exhausted"),
    ],
)
def test_openai_provider_classifies_incomplete_output(reason: str, category: str) -> None:
    value = response(None)
    payload = _safe_payload(value)
    payload.update({"status": "incomplete", "incomplete_details": {"reason": reason}})
    client = FakeClient(value, payload=payload)
    provider = OpenAIProvider(api_key="test-only", model="configured-model", client=client)
    request = build_entity_extraction_request(
        request_id="extract-incomplete",
        image=PageImageInput(sourceRef="page", mediaType="image/png", content=b"png"),
    )

    with pytest.raises(ResponseParsingError) as caught:
        asyncio.run(provider.extract(request, EntityExtractionProposal))

    metadata = caught.value.failure_metadata
    assert metadata.failure_category == category
    assert metadata.response_id == "resp_fixture"
    assert metadata.response_status == "incomplete"
    assert metadata.termination_reason == reason
    assert metadata.usage.total_tokens == 120
    assert metadata.structured_parsing_began is False


def _validation_error(model: type[AIContract], payload: str) -> ValidationError:
    try:
        model.model_validate_json(payload)
    except ValidationError as exc:
        return exc
    raise AssertionError("expected validation failure")


def test_openai_provider_classifies_malformed_structured_json() -> None:
    value = response(None)
    payload = _safe_payload(value)
    payload["output"] = [
        {"type": "message", "content": [{"type": "output_text", "text": "{"}]}
    ]
    client = FakeClient(
        value,
        payload=payload,
        parse_error=_validation_error(EntityExtractionProposal, "{"),
    )
    provider = OpenAIProvider(api_key="test-only", model="configured-model", client=client)
    request = build_entity_extraction_request(
        request_id="extract-malformed-json",
        image=PageImageInput(sourceRef="page", mediaType="image/png", content=b"png"),
    )

    with pytest.raises(MalformedStructuredOutputError) as caught:
        asyncio.run(provider.extract(request, EntityExtractionProposal))

    metadata = caught.value.failure_metadata
    assert metadata.failure_category == "malformed_structured_json"
    assert metadata.structured_parsing_began is True
    assert metadata.candidate_validation_began is False


def test_openai_provider_classifies_schema_validation_failure() -> None:
    class StrictOutput(AIContract):
        value: int

    value = response(None)
    payload = _safe_payload(value)
    payload["output"] = [
        {
            "type": "message",
            "content": [{"type": "output_text", "text": '{"value":"wrong"}'}],
        }
    ]
    client = FakeClient(
        value,
        payload=payload,
        parse_error=_validation_error(StrictOutput, '{"value":"wrong"}'),
    )
    provider = OpenAIProvider(api_key="test-only", model="configured-model", client=client)
    request = build_entity_extraction_request(
        request_id="extract-schema-invalid",
        image=PageImageInput(sourceRef="page", mediaType="image/png", content=b"png"),
    )

    with pytest.raises(MalformedStructuredOutputError) as caught:
        asyncio.run(provider.extract(request, StrictOutput))

    metadata = caught.value.failure_metadata
    assert metadata.failure_category == "structured_output_schema_validation"
    assert metadata.structured_parsing_began is True
    assert metadata.candidate_validation_began is False


@pytest.mark.parametrize(
    ("error", "expected", "category"),
    [
        (
            APIConnectionError(request=httpx.Request("POST", "https://example.invalid")),
            ProviderRequestError,
            "provider_api_failure",
        ),
        (
            APITimeoutError(httpx.Request("POST", "https://example.invalid")),
            ProviderTimeoutError,
            "timeout",
        ),
    ],
)
def test_openai_provider_classifies_transport_failures(
    error: Exception, expected: type[Exception], category: str
) -> None:
    client = FakeClient(response(None), request_error=error)
    provider = OpenAIProvider(api_key="test-only", model="configured-model", client=client)
    request = build_entity_extraction_request(
        request_id="extract-transport-failure",
        image=PageImageInput(sourceRef="page", mediaType="image/png", content=b"png"),
    )

    with pytest.raises(expected) as caught:
        asyncio.run(provider.extract(request, EntityExtractionProposal))

    assert caught.value.failure_metadata.failure_category == category
    assert caught.value.failure_metadata.structured_parsing_began is False


def test_openai_provider_rejects_only_a_semantically_invalid_candidate() -> None:
    client = FakeClient(response({"candidates": [{}], "warnings": []}))
    provider = OpenAIProvider(api_key="test-only", model="configured-model", client=client)
    request = build_entity_extraction_request(
        request_id="extract-invalid-candidate",
        image=PageImageInput(sourceRef="page", mediaType="image/png", content=b"png"),
    )

    result = asyncio.run(provider.extract(request, EntityExtractionProposal))

    diagnostics = proposal_validation_diagnostics(result.parsed_output)
    assert result.parsed_output.candidates == []
    assert diagnostics.candidates_returned == 1
    assert diagnostics.candidates_rejected == 1


def test_real_benchmark_image_can_feed_generic_page_image_contract() -> None:
    image_path = (
        Path(__file__).parents[3] / "benchmarks" / "hydrolysis" / "images" / "IMG_6807.JPG"
    )

    image = page_image_from_path(image_path)
    request = build_entity_extraction_request(request_id="benchmark-input", image=image)

    assert image.source_ref == "IMG_6807.JPG"
    assert image.media_type == "image/jpeg"
    assert image.content == image_path.read_bytes()
    assert request.output_schema == EntityExtractionProposal.model_json_schema()


def test_factory_selects_openai_from_environment_settings(tmp_path: Path) -> None:
    settings = Settings(
        database_url="sqlite://",
        storage_dir=tmp_path,
        demo_mock_graph=False,
        ai_provider="openai",
        ai_model="configured-model",
        ai_api_key="test-only",
    )

    provider = create_ai_provider(settings)

    assert isinstance(provider, OpenAIProvider)
    assert provider.model == "configured-model"

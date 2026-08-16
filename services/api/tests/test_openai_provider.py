import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.ai.contracts import PageImageInput
from app.ai.entity_proposals import (
    EntityExtractionProposal,
    build_entity_extraction_request,
    page_image_from_path,
    proposal_validation_diagnostics,
)
from app.ai.errors import ResponseParsingError
from app.ai.factory import create_ai_provider
from app.ai.openai_provider import OpenAIProvider
from app.config import Settings


class FakeResponses:
    def __init__(self, response: object):
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeClient:
    def __init__(self, response: object):
        self.responses = FakeResponses(response)


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

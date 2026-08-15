import asyncio
from copy import deepcopy

import pytest
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.ai.contracts import PageImageInput, StructuredExtractionRequest
from app.ai.errors import (
    AIErrorCode,
    MalformedStructuredOutputError,
    ProviderNotConfiguredError,
    ProviderRequestError,
    ProviderTimeoutError,
)
from app.ai.factory import create_ai_provider
from app.ai.mock import MockAIProvider, MockFixture
from app.ai.provider import execute_extraction
from app.config import Settings
from app.domain.models import EngineeringGraph


class CandidateProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    labels: list[str]
    confidence: float = Field(ge=0, le=1)


def request(request_id: str = "request-1") -> StructuredExtractionRequest:
    return StructuredExtractionRequest.for_output(
        request_id=request_id,
        image=PageImageInput(
            sourceRef="document-page:page-1", mediaType="image/png", content=b"png"
        ),
        system_instruction="Return a candidate proposal only.",
        task_prompt="Extract fixture labels.",
        output_type=CandidateProposal,
        provider_options={"temperature": 0},
    )


def run(provider: object, extraction_request: StructuredExtractionRequest | None = None):
    return asyncio.run(
        execute_extraction(
            provider, extraction_request or request(), CandidateProposal, timeout_seconds=0.05
        )
    )


def test_mock_provider_success_is_typed_deterministic_and_observable() -> None:
    provider = MockAIProvider({
        "request-1": MockFixture(
            output={"labels": ["fixture-only"], "confidence": 0.75},
            warnings=("synthetic fixture",),
        )
    })
    first = run(provider)
    second = run(provider)

    assert first == second
    assert first.parsed_output == CandidateProposal(labels=["fixture-only"], confidence=0.75)
    assert first.metadata.provider == "mock"
    assert first.metadata.model == "mock-structured-v1"
    assert first.metadata.request_id == "request-1"
    assert first.metadata.latency_ms == 0
    assert first.metadata.usage.total_tokens == 15
    assert first.metadata.raw_response_ref == "mock-fixture:request-1"


def test_missing_configuration_is_deferred_until_provider_is_requested(tmp_path) -> None:
    settings = Settings(database_url="sqlite://", storage_dir=tmp_path, demo_mock_graph=False)
    assert settings.ai_api_key is None
    with pytest.raises(ProviderNotConfiguredError) as error:
        create_ai_provider(settings)
    assert error.value.code == AIErrorCode.NOT_CONFIGURED


def test_configuration_repr_does_not_expose_api_key(tmp_path) -> None:
    secret = "super-secret-api-key"
    settings = Settings(
        database_url="sqlite://", storage_dir=tmp_path, demo_mock_graph=False,
        ai_provider="mock", ai_api_key=secret,
    )
    assert secret not in repr(settings)


def test_mock_requires_explicit_fixture_and_rejects_malformed_output() -> None:
    with pytest.raises(ProviderRequestError):
        run(MockAIProvider({}))
    malformed = MockAIProvider({
        "request-1": MockFixture(output={"labels": "not-a-list", "confidence": 2})
    })
    with pytest.raises(MalformedStructuredOutputError) as error:
        run(malformed)
    assert error.value.code == AIErrorCode.MALFORMED_OUTPUT


def test_provider_exception_and_timeout_are_normalized_without_secrets() -> None:
    secret = "super-secret-api-key"

    class FailingProvider:
        async def extract(self, extraction_request, output_type):
            raise RuntimeError(f"vendor failed with {secret}")

    class SlowProvider:
        async def extract(self, extraction_request, output_type):
            await asyncio.sleep(1)

    with pytest.raises(ProviderRequestError) as failure:
        run(FailingProvider())
    assert secret not in str(failure.value)
    assert failure.value.code == AIErrorCode.REQUEST_FAILED
    with pytest.raises(ProviderTimeoutError) as timeout:
        run(SlowProvider())
    assert timeout.value.code == AIErrorCode.TIMEOUT


def test_request_and_structured_response_validation_are_explicit() -> None:
    extraction_request = request()
    assert extraction_request.output_schema["properties"]["confidence"]["maximum"] == 1
    with pytest.raises(ValidationError, match="unsupported media input"):
        PageImageInput(sourceRef="page", mediaType="application/pdf", content=b"pdf")
    with pytest.raises(ValidationError, match="exactly one"):
        PageImageInput(sourceRef="page", mediaType="image/jpeg")


def test_ai_proposal_does_not_mutate_engineering_graph() -> None:
    graph = EngineeringGraph.model_validate({
        "schemaVersion": "0.1", "documentId": "doc-1", "entities": [],
        "connections": [], "metadata": {},
    })
    before = deepcopy(graph.model_dump(mode="json", by_alias=True))
    provider = MockAIProvider({
        "request-1": MockFixture(output={"labels": ["proposal"], "confidence": 0.5})
    })
    response = run(provider)

    assert response.parsed_output.labels == ["proposal"]
    assert graph.model_dump(mode="json", by_alias=True) == before

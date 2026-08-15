from copy import deepcopy
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from PIL import Image

import app.digitization.router as digitization_router
from app.ai.contracts import ProviderMetadata, StructuredExtractionResponse
from app.ai.entity_proposals import EntityExtractionProposal
from app.ai.topology_proposals import TopologyExtractionProposal
from app.config import Settings
from app.digitization.router import get_ai_provider
from app.main import app


def png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (12, 8), "white").save(output, format="PNG")
    return output.getvalue()


def create_document(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/documents", json={"name": "diagram", "sourceType": "image"}
    )
    assert response.status_code == 201
    return response.json()


class SequentialProvider:
    def __init__(self, *, broken_reference: bool = False):
        self.broken_reference = broken_reference
        self.output_types: list[type] = []

    async def extract(self, request, output_type):
        self.output_types.append(output_type)
        metadata = ProviderMetadata(
            provider="test",
            model="test-model",
            requestId=request.request_id,
            latencyMs=1,
            warnings=["provider warning"] if output_type is TopologyExtractionProposal else [],
        )
        if output_type is EntityExtractionProposal:
            parsed = EntityExtractionProposal.model_validate(
                {
                    "candidates": [
                        {
                            "candidateId": "entity-a",
                            "kind": "instrument",
                            "tag": "TE-1",
                            "confidence": 0.8,
                            "provenance": [{"sourceRef": "document-page:test"}],
                        },
                        {
                            "candidateId": "entity-b",
                            "kind": "equipment",
                            "tag": "V-1",
                            "confidence": 0.7,
                            "provenance": [{"sourceRef": "document-page:test"}],
                        },
                    ],
                    "warnings": ["entity ambiguity"],
                }
            )
        else:
            parsed = TopologyExtractionProposal.model_validate(
                {
                    "connections": [
                        {
                            "candidateId": "ownership-1",
                            "sourceEntityId": "missing" if self.broken_reference else "entity-a",
                            "targetEntityId": "entity-b",
                            "kind": "ownership",
                            "direction": "source_to_target",
                            "confidence": 0.6,
                            "assertion": {
                                "mode": "inferred",
                                "reviewStatus": "needs_source",
                            },
                            "provenance": [{"sourceRef": "document-page:test"}],
                        }
                    ],
                    "warnings": ["ownership is ambiguous"],
                }
            )
        return StructuredExtractionResponse(
            parsedOutput=parsed,
            metadata=metadata,
        )


def uploaded_document(client: TestClient) -> str:
    document = create_document(client)
    response = client.post(
        f"/documents/{document['id']}/upload",
        files={"file": ("diagram.png", png_bytes(), "image/png")},
    )
    assert response.status_code == 200
    return document["id"]


def configure_digitization(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: SequentialProvider,
) -> None:
    monkeypatch.setattr(
        digitization_router,
        "settings",
        Settings(database_url="sqlite://", storage_dir=tmp_path, demo_mock_graph=False),
    )
    app.dependency_overrides[get_ai_provider] = lambda: provider


def test_digitize_runs_entity_then_topology_and_does_not_mutate_graph(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = SequentialProvider()
    configure_digitization(client, tmp_path, monkeypatch, provider)
    document_id = uploaded_document(client)
    graph_before = deepcopy(client.get(f"/documents/{document_id}/graph").json())

    response = client.post(f"/documents/{document_id}/digitize")

    assert response.status_code == 200
    result = response.json()
    assert provider.output_types == [EntityExtractionProposal, TopologyExtractionProposal]
    assert result["entities"]["candidates"][0]["tag"] == "TE-1"
    connection = result["topology"]["connections"][0]
    assert connection["sourceEntityId"] == "entity-a"
    assert connection["assertion"]["mode"] == "inferred"
    assert result["warnings"] == [
        "entity ambiguity",
        "ownership is ambiguous",
        "provider warning",
    ]
    assert result["canonicalGraphMutated"] is False
    assert client.get(f"/documents/{document_id}/graph").json() == graph_before


def test_digitize_rejects_topology_reference_not_in_entity_proposal(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = SequentialProvider(broken_reference=True)
    configure_digitization(client, tmp_path, monkeypatch, provider)
    document_id = uploaded_document(client)

    response = client.post(f"/documents/{document_id}/digitize")

    assert response.status_code == 502
    assert response.json() == {"detail": "AI topology proposal failed validation"}


def test_provider_configuration_failure_is_redacted_http_503(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        digitization_router,
        "settings",
        Settings(database_url="sqlite://", storage_dir=tmp_path, demo_mock_graph=False),
    )

    with pytest.raises(HTTPException) as error:
        get_ai_provider()

    assert error.value.status_code == 503
    assert error.value.detail == "AI provider is not configured"

from pathlib import Path
from uuid import uuid4

from app.ai.contracts import PageImageInput
from app.ai.entity_proposals import EntityExtractionProposal, build_entity_extraction_request
from app.ai.provider import AIProvider, execute_extraction
from app.ai.topology_proposals import (
    TopologyExtractionProposal,
    build_topology_extraction_request,
    validate_topology_references,
)
from app.digitization.schemas import DigitizationProposalResponse


async def extract_page_proposal(
    *,
    provider: AIProvider,
    document_id: str,
    page_id: str,
    image_path: Path,
    width_px: int,
    height_px: int,
) -> DigitizationProposalResponse:
    image = PageImageInput(
        source_ref=f"document-page:{page_id}",
        media_type="image/png",
        content=image_path.read_bytes(),
        width_px=width_px,
        height_px=height_px,
    )
    extraction_id = str(uuid4())
    entity_request = build_entity_extraction_request(
        request_id=f"{extraction_id}:entities",
        image=image,
        provider_options={"max_output_tokens": 12000, "reasoning": {"effort": "low"}},
    )
    entity_response = await execute_extraction(
        provider, entity_request, EntityExtractionProposal, timeout_seconds=180
    )
    topology_request = build_topology_extraction_request(
        request_id=f"{extraction_id}:topology",
        image=image,
        entities=entity_response.parsed_output.candidates,
        provider_options={"max_output_tokens": 12000, "reasoning": {"effort": "low"}},
    )
    topology_response = await execute_extraction(
        provider, topology_request, TopologyExtractionProposal, timeout_seconds=180
    )
    validate_topology_references(
        topology_response.parsed_output, entity_response.parsed_output.candidates
    )
    warnings = [
        *entity_response.parsed_output.warnings,
        *entity_response.metadata.warnings,
        *topology_response.parsed_output.warnings,
        *topology_response.metadata.warnings,
    ]
    return DigitizationProposalResponse(
        document_id=document_id,
        page_id=page_id,
        entities=entity_response.parsed_output,
        topology=topology_response.parsed_output,
        entity_provider_metadata=entity_response.metadata,
        topology_provider_metadata=topology_response.metadata,
        warnings=warnings,
    )

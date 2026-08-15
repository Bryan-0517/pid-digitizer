from pathlib import Path
from typing import Literal

from pydantic import Field

from app.ai.contracts import AIContract, PageImageInput, StructuredExtractionRequest
from app.domain.models import EntityGeometry, JsonValue


class CandidateProvenance(AIContract):
    source_ref: str
    evidence_text: str | None = None
    note: str | None = None


class CandidateProperty(AIContract):
    name: str
    value: str | int | float | bool | None
    evidence_text: str | None = None


class EntityCandidate(AIContract):
    candidate_id: str
    kind: Literal["equipment", "valve", "instrument", "boundary", "text", "unknown"]
    subtype: str | None = None
    tag: str | None = None
    display_name: str | None = None
    properties: list[CandidateProperty] = Field(default_factory=list)
    geometry: EntityGeometry | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    provenance: list[CandidateProvenance] = Field(min_length=1)


class EntityExtractionProposal(AIContract):
    candidates: list[EntityCandidate]
    warnings: list[str] = Field(default_factory=list)


def build_entity_extraction_request(
    *, request_id: str, image: PageImageInput,
    provider_options: dict[str, JsonValue] | None = None,
) -> StructuredExtractionRequest:
    return StructuredExtractionRequest.for_output(
        request_id=request_id,
        image=image,
        system_instruction=(
            "Identify only visible candidate equipment, valves, instruments, boundary nodes, and "
            "text/tag candidates. Return proposals, not verified engineering truth. Do not infer "
            "connections or fabricate tags, properties, confidence, evidence, or geometry."
        ),
        task_prompt=(
            "Inspect the supplied engineering page image. Report candidate objects supported by "
            "the image. Include provenance for every candidate and confidence only when available."
        ),
        output_type=EntityExtractionProposal,
        provider_options=provider_options,
    )


def page_image_from_path(path: Path, *, source_ref: str | None = None) -> PageImageInput:
    media_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
    media_type = media_types.get(path.suffix.lower())
    if media_type is None:
        raise ValueError("unsupported page image file type")
    return PageImageInput(
        source_ref=source_ref or path.name,
        media_type=media_type,
        content=path.read_bytes(),
    )

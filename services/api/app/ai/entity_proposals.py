from pathlib import Path
import json
from typing import Literal

from pydantic import Field, ValidationError, model_validator

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


class CandidateValidationWarning(AIContract):
    candidate_index: int = Field(ge=0)
    candidate_id: str | None = None
    component: Literal["geometry", "semantic"]
    reason: str
    action: Literal["geometry_removed", "candidate_rejected"]


class ProposalValidationDiagnostics(AIContract):
    candidates_returned: int
    candidates_fully_valid: int
    candidates_retained_without_geometry: int
    candidates_rejected: int
    geometry_validation_warnings: list[CandidateValidationWarning]


_VALIDATION_WARNING_PREFIX = "candidate_validation:"


class EntityExtractionProposal(AIContract):
    candidates: list[EntityCandidate]
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def isolate_candidate_validation(cls, value: object) -> object:
        if not isinstance(value, dict) or not isinstance(value.get("candidates"), list):
            return value
        raw_candidates = value["candidates"]
        retained: list[EntityCandidate] = []
        diagnostics: list[CandidateValidationWarning] = []
        for index, raw_candidate in enumerate(raw_candidates):
            if isinstance(raw_candidate, EntityCandidate):
                retained.append(raw_candidate)
                continue
            candidate_id = (
                raw_candidate.get("candidateId") or raw_candidate.get("candidate_id")
                if isinstance(raw_candidate, dict)
                else None
            )
            if not isinstance(raw_candidate, dict):
                diagnostics.append(
                    CandidateValidationWarning(
                        candidate_index=index,
                        candidate_id=candidate_id if isinstance(candidate_id, str) else None,
                        component="semantic",
                        reason="candidate must be an object",
                        action="candidate_rejected",
                    )
                )
                continue
            semantic_payload = dict(raw_candidate)
            raw_geometry = semantic_payload.pop("geometry", None)
            try:
                semantic_candidate = EntityCandidate.model_validate(
                    {**semantic_payload, "geometry": None}
                )
            except ValidationError as exc:
                diagnostics.append(
                    CandidateValidationWarning(
                        candidate_index=index,
                        candidate_id=candidate_id if isinstance(candidate_id, str) else None,
                        component="semantic",
                        reason=_safe_validation_reason(exc),
                        action="candidate_rejected",
                    )
                )
                continue
            if raw_geometry is None:
                retained.append(semantic_candidate)
                continue
            try:
                geometry = EntityGeometry.model_validate(raw_geometry)
            except ValidationError as exc:
                diagnostics.append(
                    CandidateValidationWarning(
                        candidate_index=index,
                        candidate_id=semantic_candidate.candidate_id,
                        component="geometry",
                        reason=_safe_validation_reason(exc),
                        action="geometry_removed",
                    )
                )
                retained.append(semantic_candidate)
                continue
            retained.append(semantic_candidate.model_copy(update={"geometry": geometry}))
        provider_warnings = [
            warning
            for warning in value.get("warnings", [])
            if isinstance(warning, str) and not warning.startswith(_VALIDATION_WARNING_PREFIX)
        ]
        provider_warnings.extend(
            _VALIDATION_WARNING_PREFIX
            + json.dumps(warning.model_dump(mode="json", by_alias=True), sort_keys=True)
            for warning in diagnostics
        )
        return {**value, "candidates": retained, "warnings": provider_warnings}


def proposal_validation_diagnostics(
    proposal: EntityExtractionProposal,
) -> ProposalValidationDiagnostics:
    validation_warnings = []
    for warning in proposal.warnings:
        if warning.startswith(_VALIDATION_WARNING_PREFIX):
            validation_warnings.append(
                CandidateValidationWarning.model_validate_json(
                    warning.removeprefix(_VALIDATION_WARNING_PREFIX)
                )
            )
    rejected = sum(item.action == "candidate_rejected" for item in validation_warnings)
    geometry_removed = sum(item.action == "geometry_removed" for item in validation_warnings)
    returned = len(proposal.candidates) + rejected
    return ProposalValidationDiagnostics(
        candidates_returned=returned,
        candidates_fully_valid=len(proposal.candidates) - geometry_removed,
        candidates_retained_without_geometry=geometry_removed,
        candidates_rejected=rejected,
        geometry_validation_warnings=[
            item for item in validation_warnings if item.component == "geometry"
        ],
    )


def _safe_validation_reason(error: ValidationError) -> str:
    first = error.errors(include_url=False, include_input=False)[0]
    location = ".".join(str(part) for part in first["loc"])
    return f"{location}: {first['msg']}" if location else first["msg"]


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

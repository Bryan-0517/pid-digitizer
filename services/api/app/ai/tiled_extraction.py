from __future__ import annotations

from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Literal

from PIL import Image
from pydantic import Field

from app.ai.contracts import AIContract, PageImageInput, ProviderMetadata, StructuredExtractionRequest
from app.ai.entity_proposals import (
    CandidateValidationWarning,
    EntityCandidate,
    EntityExtractionProposal,
    proposal_validation_diagnostics,
)
from app.ai.provider import AIProvider, execute_extraction
from app.domain.models import BoundingBox, EntityGeometry, Point

ExtractionPass = Literal["equipment_boundary", "instruments", "valves"]
PASS_ORDER: tuple[ExtractionPass, ...] = ("equipment_boundary", "instruments", "valves")


class PixelRegion(AIContract):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class TileSpec(AIContract):
    tile_id: str
    row: int
    column: int
    region_in_roi: PixelRegion
    region_in_original: PixelRegion


class TilingPolicy(AIContract):
    rows: int = 2
    columns: int = 2
    overlap_fraction: float = 0.15
    roi: PixelRegion
    tiles: list[TileSpec]


class TileCallResult(AIContract):
    extraction_pass: ExtractionPass
    tile: TileSpec
    candidate_count: int
    candidates_returned: int
    candidates_fully_valid: int
    candidates_retained_without_geometry: int
    candidates_rejected: int
    geometry_validation_warnings: list[CandidateValidationWarning]
    provider_metadata: ProviderMetadata
    warnings: list[str]


class TiledRunManifest(AIContract):
    schema_version: Literal["0.1"] = "0.1"
    experiment_id: str
    benchmark_document_id: str
    benchmark_page_id: str
    source_filename: str
    source_sha256: str
    provider_name: str
    provider_model: str | None = None
    original_width_px: int
    original_height_px: int
    tiling_policy: TilingPolicy
    extraction_passes: list[ExtractionPass]
    maximum_output_tokens_per_call: int
    image_detail: Literal["high"] = "high"
    reasoning_effort: Literal["low"] = "low"
    extraction_configuration_sha256: str
    call_request_ids: list[str]


class TileCallCheckpoint(AIContract):
    schema_version: Literal["0.1"] = "0.1"
    call_number: int = Field(ge=1, le=12)
    request_id: str
    result: TileCallResult
    proposal: EntityExtractionProposal


class TiledExtractionSnapshot(AIContract):
    snapshot_label: Literal["MODEL OUTPUT SNAPSHOT — NOT BENCHMARK TRUTH"] = (
        "MODEL OUTPUT SNAPSHOT — NOT BENCHMARK TRUTH"
    )
    experiment_id: str
    benchmark_document_id: str
    benchmark_page_id: str
    source_filename: str
    original_width_px: int
    original_height_px: int
    tiling_policy: TilingPolicy
    extraction_passes: list[ExtractionPass]
    maximum_output_tokens_per_call: int
    merged_proposal: EntityExtractionProposal
    topology_proposal_count: int = 0
    calls: list[TileCallResult]
    duplicate_proposals_removed: int
    ambiguous_deduplication_groups: list[list[str]]
    canonical_graph_mutated: bool = False


def build_tiles(roi: PixelRegion, *, rows: int = 2, columns: int = 2, overlap: float = 0.15) -> list[TileSpec]:
    if rows < 1 or columns < 1 or not 0 <= overlap < 1:
        raise ValueError("invalid tiling policy")
    tiles = []
    nominal_width = roi.width / columns
    nominal_height = roi.height / rows
    expand_x = nominal_width * overlap / 2
    expand_y = nominal_height * overlap / 2
    for row in range(rows):
        for column in range(columns):
            left = round(max(0, column * nominal_width - (expand_x if column else 0)))
            right = round(
                min(roi.width, (column + 1) * nominal_width + (expand_x if column < columns - 1 else 0))
            )
            top = round(max(0, row * nominal_height - (expand_y if row else 0)))
            bottom = round(
                min(roi.height, (row + 1) * nominal_height + (expand_y if row < rows - 1 else 0))
            )
            local = PixelRegion(x=left, y=top, width=right - left, height=bottom - top)
            original = PixelRegion(
                x=roi.x + left,
                y=roi.y + top,
                width=local.width,
                height=local.height,
            )
            tiles.append(
                TileSpec(
                    tile_id=f"r{row}c{column}",
                    row=row,
                    column=column,
                    region_in_roi=local,
                    region_in_original=original,
                )
            )
    return tiles


def build_tile_request(
    *,
    request_id: str,
    image: PageImageInput,
    extraction_pass: ExtractionPass,
    maximum_output_tokens: int,
) -> StructuredExtractionRequest:
    focus = {
        "equipment_boundary": (
            "equipment and process boundary nodes",
            "Return kinds equipment or boundary only. Include every visible vessel, tank, pump, "
            "agitator, header, inlet, outlet, and other equipment/boundary supported by the tile.",
        ),
        "instruments": (
            "instruments",
            "Return kind instrument only. Exhaustively inspect visible engineering labels including "
            "FIT, FI, LIT, LT, PIT, PI, TIT, TI, TE, PT, and comparable instrument-style labels. "
            "These are examples of label families, not expected tag answers.",
        ),
        "valves": (
            "valves",
            "Return kind valve only. Include every visible engineering valve with a supported tag "
            "or clearly visible valve symbol; do not infer hidden valves.",
        ),
    }[extraction_pass]
    return StructuredExtractionRequest.for_output(
        request_id=request_id,
        image=image,
        system_instruction=(
            f"Exhaustively enumerate all visible {focus[0]} in this tile of a dense DCS process "
            "display. This is a proposal, not verified engineering truth. Do not return a "
            "representative sample. Do not extract application chrome, menus, navigation, logos, "
            "monitor branding, timestamps, buttons, or generic UI text. Do not fabricate tags, "
            "properties, confidence, or geometry. Bboxes must be normalized to this tile."
        ),
        task_prompt=focus[1] + " Include evidence/provenance for every candidate.",
        output_type=EntityExtractionProposal,
        provider_options={
            "image_detail": "high",
            "max_output_tokens": maximum_output_tokens,
            "reasoning": {"effort": "low"},
        },
    )


async def run_tiled_extraction(
    *,
    provider: AIProvider,
    image_path: Path,
    experiment_id: str,
    benchmark_document_id: str,
    benchmark_page_id: str,
    roi: PixelRegion,
    maximum_output_tokens: int = 6000,
    checkpoint_dir: Path | None = None,
    final_output_path: Path | None = None,
) -> TiledExtractionSnapshot:
    source_bytes = image_path.read_bytes()
    with Image.open(image_path) as source:
        source.load()
        original = source.convert("RGB")
    if roi.x + roi.width > original.width or roi.y + roi.height > original.height:
        raise ValueError("ROI exceeds source image bounds")
    tiles = build_tiles(roi)
    call_plan = [(extraction_pass, tile) for extraction_pass in PASS_ORDER for tile in tiles]
    manifest = TiledRunManifest(
        experiment_id=experiment_id,
        benchmark_document_id=benchmark_document_id,
        benchmark_page_id=benchmark_page_id,
        source_filename=image_path.name,
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        provider_name=getattr(provider, "provider_name", type(provider).__name__),
        provider_model=getattr(provider, "model", None),
        original_width_px=original.width,
        original_height_px=original.height,
        tiling_policy=TilingPolicy(roi=roi, tiles=tiles),
        extraction_passes=list(PASS_ORDER),
        maximum_output_tokens_per_call=maximum_output_tokens,
        extraction_configuration_sha256=_extraction_configuration_sha256(
            maximum_output_tokens
        ),
        call_request_ids=[
            f"{experiment_id}:{extraction_pass}:{tile.tile_id}"
            for extraction_pass, tile in call_plan
        ],
    )
    checkpoints: dict[str, TileCallCheckpoint] = {}
    if checkpoint_dir is not None:
        checkpoints = _prepare_checkpoint_run(checkpoint_dir, manifest)
    candidates: list[EntityCandidate] = []
    calls: list[TileCallResult] = []
    for call_number, (extraction_pass, tile) in enumerate(call_plan, start=1):
        request_id = f"{experiment_id}:{extraction_pass}:{tile.tile_id}"
        checkpoint = checkpoints.get(request_id)
        if checkpoint is not None:
            candidates.extend(checkpoint.proposal.candidates)
            calls.append(checkpoint.result)
            continue
        region = tile.region_in_original
        tile_image = original.crop(
            (region.x, region.y, region.x + region.width, region.y + region.height)
        )
        buffer = BytesIO()
        tile_image.save(buffer, format="PNG")
        request = build_tile_request(
            request_id=request_id,
            image=PageImageInput(
                source_ref=f"{image_path.name}#tile:{tile.tile_id}",
                media_type="image/png",
                content=buffer.getvalue(),
                width_px=region.width,
                height_px=region.height,
            ),
            extraction_pass=extraction_pass,
            maximum_output_tokens=maximum_output_tokens,
        )
        response = await execute_extraction(
            provider, request, EntityExtractionProposal, timeout_seconds=240
        )
        diagnostics = proposal_validation_diagnostics(response.parsed_output)
        transformed = [
            transform_candidate(
                candidate,
                tile=tile,
                original_width=original.width,
                original_height=original.height,
                extraction_pass=extraction_pass,
            )
            for candidate in response.parsed_output.candidates
        ]
        result = TileCallResult(
            extraction_pass=extraction_pass,
            tile=tile,
            candidate_count=len(transformed),
            candidates_returned=diagnostics.candidates_returned,
            candidates_fully_valid=diagnostics.candidates_fully_valid,
            candidates_retained_without_geometry=(
                diagnostics.candidates_retained_without_geometry
            ),
            candidates_rejected=diagnostics.candidates_rejected,
            geometry_validation_warnings=diagnostics.geometry_validation_warnings,
            provider_metadata=response.metadata,
            warnings=response.parsed_output.warnings,
        )
        proposal = EntityExtractionProposal(
            candidates=transformed, warnings=response.parsed_output.warnings
        )
        checkpoint = TileCallCheckpoint(
            call_number=call_number, request_id=request_id, result=result, proposal=proposal
        )
        if checkpoint_dir is not None:
            _write_json_atomic(
                checkpoint_dir / "calls" / f"{call_number:02d}.json", checkpoint
            )
        candidates.extend(transformed)
        calls.append(result)
    merged, removed, ambiguous = deduplicate_candidates(candidates)
    warnings = [warning for call in calls for warning in call.warnings]
    snapshot = TiledExtractionSnapshot(
        experiment_id=experiment_id,
        benchmark_document_id=benchmark_document_id,
        benchmark_page_id=benchmark_page_id,
        source_filename=image_path.name,
        original_width_px=original.width,
        original_height_px=original.height,
        tiling_policy=TilingPolicy(roi=roi, tiles=tiles),
        extraction_passes=list(PASS_ORDER),
        maximum_output_tokens_per_call=maximum_output_tokens,
        merged_proposal=EntityExtractionProposal(candidates=merged, warnings=warnings),
        calls=calls,
        duplicate_proposals_removed=removed,
        ambiguous_deduplication_groups=ambiguous,
    )
    if final_output_path is not None:
        _write_json_atomic(final_output_path, snapshot)
    return snapshot


def _prepare_checkpoint_run(
    checkpoint_dir: Path, expected: TiledRunManifest
) -> dict[str, TileCallCheckpoint]:
    manifest_path = checkpoint_dir / "manifest.json"
    calls_dir = checkpoint_dir / "calls"
    if manifest_path.exists():
        actual = TiledRunManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        if actual != expected:
            raise ValueError("checkpoint configuration mismatch; refusing unsafe resume")
    else:
        if checkpoint_dir.exists() and any(checkpoint_dir.iterdir()):
            raise ValueError("checkpoint directory is non-empty but has no manifest")
        calls_dir.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(manifest_path, expected)
    calls_dir.mkdir(parents=True, exist_ok=True)
    loaded: dict[str, TileCallCheckpoint] = {}
    for path in sorted(calls_dir.glob("*.json")):
        checkpoint = TileCallCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
        expected_number = len(loaded) + 1
        if checkpoint.call_number != expected_number or path.name != f"{expected_number:02d}.json":
            raise ValueError("checkpoint sequence is incomplete or out of order")
        expected_request_id = expected.call_request_ids[expected_number - 1]
        if checkpoint.request_id != expected_request_id:
            raise ValueError("checkpoint call plan mismatch; refusing unsafe resume")
        expected_pass = expected.extraction_passes[(expected_number - 1) // 4]
        expected_tile = expected.tiling_policy.tiles[(expected_number - 1) % 4]
        if (
            checkpoint.result.extraction_pass != expected_pass
            or checkpoint.result.tile != expected_tile
            or checkpoint.result.provider_metadata.request_id != expected_request_id
        ):
            raise ValueError("checkpoint content mismatch; refusing unsafe resume")
        loaded[checkpoint.request_id] = checkpoint
    return loaded


def _extraction_configuration_sha256(maximum_output_tokens: int) -> str:
    image = PageImageInput(source_ref="configuration", media_type="image/png", content=b"x")
    configurations = []
    for extraction_pass in PASS_ORDER:
        request = build_tile_request(
            request_id="configuration",
            image=image,
            extraction_pass=extraction_pass,
            maximum_output_tokens=maximum_output_tokens,
        )
        configurations.append(
            {
                "validationPolicyVersion": "candidate-isolation-v1",
                "pass": extraction_pass,
                "systemInstruction": request.system_instruction,
                "taskPrompt": request.task_prompt,
                "outputSchema": request.output_schema,
                "providerOptions": request.provider_options,
            }
        )
    canonical = json.dumps(configurations, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _write_json_atomic(path: Path, value: AIContract) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    payload = value.model_dump(mode="json", by_alias=True)
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def transform_candidate(
    candidate: EntityCandidate,
    *,
    tile: TileSpec,
    original_width: int,
    original_height: int,
    extraction_pass: ExtractionPass,
) -> EntityCandidate:
    region = tile.region_in_original
    geometry = candidate.geometry
    transformed_geometry = None
    if geometry is not None:
        transformed_geometry = EntityGeometry(
            bbox=_transform_bbox(geometry.bbox, region, original_width, original_height)
            if geometry.bbox
            else None,
            polygon=[
                _transform_point(point, region, original_width, original_height)
                for point in geometry.polygon
            ]
            if geometry.polygon
            else None,
            anchor_points=[
                _transform_point(point, region, original_width, original_height)
                for point in geometry.anchor_points
            ]
            if geometry.anchor_points
            else None,
        )
    provenance = [
        item.model_copy(
            update={
                "source_ref": f"IMG_6807.JPG#tile:{tile.tile_id}",
                "note": _join_note(item.note, f"pass={extraction_pass}; tile-local geometry restored to original image"),
            }
        )
        for item in candidate.provenance
    ]
    return candidate.model_copy(
        update={
            "candidate_id": f"{extraction_pass}:{tile.tile_id}:{candidate.candidate_id}",
            "geometry": transformed_geometry,
            "provenance": provenance,
        }
    )


def _transform_bbox(
    bbox: BoundingBox, region: PixelRegion, original_width: int, original_height: int
) -> BoundingBox:
    return BoundingBox(
        x=(region.x + bbox.x * region.width) / original_width,
        y=(region.y + bbox.y * region.height) / original_height,
        width=bbox.width * region.width / original_width,
        height=bbox.height * region.height / original_height,
    )


def _transform_point(
    point: Point, region: PixelRegion, original_width: int, original_height: int
) -> Point:
    return Point(
        x=(region.x + point.x * region.width) / original_width,
        y=(region.y + point.y * region.height) / original_height,
    )


def deduplicate_candidates(
    candidates: list[EntityCandidate],
) -> tuple[list[EntityCandidate], int, list[list[str]]]:
    kept: list[EntityCandidate] = []
    removed = 0
    ambiguous: list[list[str]] = []
    for candidate in sorted(candidates, key=lambda item: item.candidate_id):
        duplicate_index = next(
            (index for index, current in enumerate(kept) if _is_duplicate(current, candidate)), None
        )
        if duplicate_index is not None:
            kept[duplicate_index] = _preferred(kept[duplicate_index], candidate)
            removed += 1
            continue
        conflicting = [
            current.candidate_id
            for current in kept
            if _same_tag_and_kind(current, candidate) and not _spatially_close(current, candidate)
        ]
        if conflicting:
            ambiguous.append(sorted([*conflicting, candidate.candidate_id]))
        kept.append(candidate)
    return kept, removed, sorted(ambiguous)


def _is_duplicate(left: EntityCandidate, right: EntityCandidate) -> bool:
    if left.kind != right.kind:
        return False
    left_tag = normalize_comparison_text(left.tag)
    right_tag = normalize_comparison_text(right.tag)
    if left_tag and right_tag:
        return left_tag == right_tag and _spatially_close(left, right)
    return not left_tag and not right_tag and _bbox_iou(left, right) >= 0.85


def _same_tag_and_kind(left: EntityCandidate, right: EntityCandidate) -> bool:
    left_tag = normalize_comparison_text(left.tag)
    return bool(left.kind == right.kind and left_tag and left_tag == normalize_comparison_text(right.tag))


def _spatially_close(left: EntityCandidate, right: EntityCandidate) -> bool:
    if _bbox_iou(left, right) >= 0.2:
        return True
    left_box = left.geometry.bbox if left.geometry else None
    right_box = right.geometry.bbox if right.geometry else None
    if not left_box or not right_box:
        return False
    left_center = (left_box.x + left_box.width / 2, left_box.y + left_box.height / 2)
    right_center = (right_box.x + right_box.width / 2, right_box.y + right_box.height / 2)
    return abs(left_center[0] - right_center[0]) <= 0.05 and abs(left_center[1] - right_center[1]) <= 0.05


def _bbox_iou(left: EntityCandidate, right: EntityCandidate) -> float:
    left_box = left.geometry.bbox if left.geometry else None
    right_box = right.geometry.bbox if right.geometry else None
    if not left_box or not right_box:
        return 0
    intersection_width = max(
        0, min(left_box.x + left_box.width, right_box.x + right_box.width) - max(left_box.x, right_box.x)
    )
    intersection_height = max(
        0, min(left_box.y + left_box.height, right_box.y + right_box.height) - max(left_box.y, right_box.y)
    )
    intersection = intersection_width * intersection_height
    union = left_box.width * left_box.height + right_box.width * right_box.height - intersection
    return intersection / union if union else 0


def _preferred(left: EntityCandidate, right: EntityCandidate) -> EntityCandidate:
    def key(candidate: EntityCandidate):
        return (candidate.confidence is not None, candidate.confidence or 0, -len(candidate.candidate_id))

    return max((left, right), key=key)


def _join_note(existing: str | None, addition: str) -> str:
    return f"{existing}; {addition}" if existing else addition


def normalize_comparison_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s*([_-])\s*", r"\1", value.strip().casefold())
    return normalized or None

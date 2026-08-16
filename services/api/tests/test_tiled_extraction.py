import asyncio
import json
from pathlib import Path

from PIL import Image
import pytest

from app.ai.contracts import PageImageInput, ProviderFailureMetadata
from app.ai.entity_proposals import (
    EntityCandidate,
    EntityExtractionProposal,
    proposal_validation_diagnostics,
)
from app.ai.mock import MockAIProvider, MockFixture
from app.ai.errors import ProviderRequestError
from app.ai.tiled_extraction import (
    PASS_ORDER,
    PixelRegion,
    TileSpec,
    build_tile_request,
    build_tiles,
    deduplicate_candidates,
    run_tiled_extraction,
    transform_candidate,
)
from app.evaluation.taxonomy import classify_proposal_taxonomy


def candidate(candidate_id: str, *, kind: str = "instrument", tag: str | None = "TE_1", x: float = 0.1):
    return EntityCandidate.model_validate(
        {
            "candidateId": candidate_id,
            "kind": kind,
            "tag": tag,
            "geometry": {"bbox": {"x": x, "y": 0.2, "width": 0.1, "height": 0.1}},
            "provenance": [{"sourceRef": "tile"}],
        }
    )


def test_fixed_grid_has_four_overlapping_tiles_and_full_roi_coverage() -> None:
    roi = PixelRegion(x=96, y=636, width=4864, height=2748)

    tiles = build_tiles(roi)

    assert [tile.tile_id for tile in tiles] == ["r0c0", "r0c1", "r1c0", "r1c1"]
    assert tiles[0].region_in_original.x == roi.x
    assert tiles[0].region_in_original.y == roi.y
    assert tiles[-1].region_in_original.x + tiles[-1].region_in_original.width == roi.x + roi.width
    assert tiles[-1].region_in_original.y + tiles[-1].region_in_original.height == roi.y + roi.height
    horizontal_overlap = (
        tiles[0].region_in_original.x
        + tiles[0].region_in_original.width
        - tiles[1].region_in_original.x
    )
    assert horizontal_overlap > 0


def test_tile_bbox_is_restored_to_original_normalized_coordinates() -> None:
    tile = TileSpec(
        tileId="r0c0",
        row=0,
        column=0,
        regionInRoi={"x": 0, "y": 0, "width": 400, "height": 200},
        regionInOriginal={"x": 100, "y": 50, "width": 400, "height": 200},
    )

    transformed = transform_candidate(
        candidate("local"),
        tile=tile,
        original_width=1000,
        original_height=500,
        extraction_pass="instruments",
    )

    assert transformed.candidate_id == "instruments:r0c0:local"
    assert transformed.geometry.bbox.model_dump() == {
        "x": 0.14,
        "y": 0.18,
        "width": 0.04,
        "height": 0.04,
    }
    assert transformed.provenance[0].source_ref == "IMG_6807.JPG#tile:r0c0"


def test_candidate_validation_isolates_invalid_geometry_and_semantics() -> None:
    proposal = EntityExtractionProposal.model_validate(
        {
            "candidates": [
                {
                    "candidateId": "valid",
                    "kind": "equipment",
                    "geometry": {
                        "bbox": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}
                    },
                    "provenance": [{"sourceRef": "tile"}],
                },
                {
                    "candidateId": "bad-geometry",
                    "kind": "equipment",
                    "geometry": {
                        "bbox": {"x": 0.86, "y": 0.44, "width": 0.17, "height": 0.1}
                    },
                    "provenance": [{"sourceRef": "tile"}],
                },
                {
                    "candidateId": "bad-semantics",
                    "kind": "not-a-kind",
                    "provenance": [{"sourceRef": "tile"}],
                },
            ],
            "warnings": [],
        }
    )

    assert [item.candidate_id for item in proposal.candidates] == ["valid", "bad-geometry"]
    assert proposal.candidates[0].geometry is not None
    assert proposal.candidates[1].geometry is None
    diagnostics = proposal_validation_diagnostics(proposal)
    assert diagnostics.candidates_returned == 3
    assert diagnostics.candidates_fully_valid == 1
    assert diagnostics.candidates_retained_without_geometry == 1
    assert diagnostics.candidates_rejected == 1
    assert diagnostics.geometry_validation_warnings[0].candidate_id == "bad-geometry"
    assert "normalized [0,1]" in diagnostics.geometry_validation_warnings[0].reason


def test_substantial_out_of_range_bbox_is_not_clamped() -> None:
    proposal = EntityExtractionProposal.model_validate(
        {
            "candidates": [
                {
                    "candidateId": "outside",
                    "kind": "boundary",
                    "geometry": {
                        "bbox": {"x": 0.86, "y": 0.44, "width": 0.17, "height": 0.1}
                    },
                    "provenance": [{"sourceRef": "tile"}],
                }
            ]
        }
    )

    assert proposal.candidates[0].geometry is None


def test_transformed_geometry_is_revalidated_against_full_image() -> None:
    tile = TileSpec(
        tileId="outside",
        row=0,
        column=0,
        regionInRoi={"x": 0, "y": 0, "width": 100, "height": 100},
        regionInOriginal={"x": 950, "y": 0, "width": 100, "height": 100},
    )

    with pytest.raises(ValueError, match="less than or equal to 1"):
        transform_candidate(
            candidate("local", x=0.6),
            tile=tile,
            original_width=1000,
            original_height=1000,
            extraction_pass="equipment_boundary",
        )


def test_pass_prompts_are_exhaustive_scoped_and_reference_answer_free() -> None:
    image = PageImageInput(sourceRef="tile", mediaType="image/png", content=b"png")
    requests = {
        extraction_pass: build_tile_request(
            request_id=extraction_pass,
            image=image,
            extraction_pass=extraction_pass,
            maximum_output_tokens=6000,
        )
        for extraction_pass in PASS_ORDER
    }

    assert all("exhaust" in request.system_instruction.casefold() for request in requests.values())
    assert all("representative sample" in request.system_instruction for request in requests.values())
    assert "FIT, FI, LIT, LT, PIT, PI, TIT, TI, TE, PT" in requests["instruments"].task_prompt
    combined = " ".join(
        request.system_instruction + request.task_prompt for request in requests.values()
    )
    assert "A310001A" not in combined
    assert "64" not in combined


def test_deduplication_requires_kind_tag_and_spatial_evidence() -> None:
    near_a = candidate("a", tag="TE_1", x=0.10)
    near_b = candidate("b", tag=" te_ 1 ", x=0.11)
    far = candidate("far", tag="TE_1", x=0.8)
    incompatible = candidate("valve", kind="valve", tag="TE_1", x=0.11)

    merged, removed, ambiguous = deduplicate_candidates([near_a, near_b, far, incompatible])

    assert removed == 1
    assert len(merged) == 3
    assert ambiguous == [["a", "far"]]


def test_complete_mock_experiment_uses_fixed_twelve_call_plan(tmp_path: Path) -> None:
    image_path = tmp_path / "screen.jpg"
    Image.new("RGB", (100, 100), "white").save(image_path, format="JPEG")
    experiment_id = "fixed-plan"
    fixtures = {}
    for extraction_pass in PASS_ORDER:
        for tile in build_tiles(PixelRegion(x=0, y=0, width=100, height=100)):
            fixtures[f"{experiment_id}:{extraction_pass}:{tile.tile_id}"] = MockFixture(
                output={"candidates": [], "warnings": []}
            )

    snapshot = asyncio.run(
        run_tiled_extraction(
            provider=MockAIProvider(fixtures),
            image_path=image_path,
            experiment_id=experiment_id,
            benchmark_document_id="benchmark:hydrolysis",
            benchmark_page_id="benchmark:hydrolysis:IMG_6807.JPG",
            roi=PixelRegion(x=0, y=0, width=100, height=100),
        )
    )

    assert len(snapshot.calls) == 12
    assert snapshot.extraction_passes == list(PASS_ORDER)
    assert snapshot.maximum_output_tokens_per_call == 6000
    assert snapshot.canonical_graph_mutated is False


def test_checkpoint_persists_safe_candidate_validation_diagnostics(tmp_path: Path) -> None:
    image_path = tmp_path / "screen.jpg"
    Image.new("RGB", (100, 100), "white").save(image_path, format="JPEG")
    run_dir = tmp_path / "runs" / "diagnostics"
    request_ids = [
        f"diagnostics:{extraction_pass}:{tile.tile_id}"
        for extraction_pass in PASS_ORDER
        for tile in build_tiles(PixelRegion(x=0, y=0, width=100, height=100))
    ]
    fixtures = {
        request_id: MockFixture(output={"candidates": [], "warnings": []})
        for request_id in request_ids
    }
    fixtures[request_ids[0]] = MockFixture(
        output={
            "candidates": [
                {
                    "candidateId": "valid",
                    "kind": "equipment",
                    "provenance": [{"sourceRef": "tile"}],
                },
                {
                    "candidateId": "invalid-geometry",
                    "kind": "equipment",
                    "geometry": {
                        "bbox": {"x": 0.86, "y": 0.44, "width": 0.17, "height": 0.1}
                    },
                    "provenance": [{"sourceRef": "tile"}],
                },
            ]
        }
    )

    snapshot = asyncio.run(
        run_tiled_extraction(
            provider=MockAIProvider(fixtures),
            image_path=image_path,
            experiment_id="diagnostics",
            benchmark_document_id="benchmark:hydrolysis",
            benchmark_page_id="benchmark:hydrolysis:IMG_6807.JPG",
            roi=PixelRegion(x=0, y=0, width=100, height=100),
            checkpoint_dir=run_dir,
        )
    )

    first = snapshot.calls[0]
    assert first.candidates_returned == 2
    assert first.candidates_fully_valid == 1
    assert first.candidates_retained_without_geometry == 1
    assert first.candidates_rejected == 0
    assert first.geometry_validation_warnings[0].candidate_id == "invalid-geometry"
    checkpoint = (run_dir / "calls" / "01.json").read_text(encoding="utf-8")
    assert '"candidatesRetainedWithoutGeometry": 1' in checkpoint
    assert '"geometryValidationWarnings"' in checkpoint


def test_interrupted_run_persists_five_calls_and_resume_starts_at_six(tmp_path: Path) -> None:
    image_path = tmp_path / "screen.jpg"
    Image.new("RGB", (100, 100), "white").save(image_path, format="JPEG")
    run_dir = tmp_path / "runs" / "interrupted"
    final_output_path = tmp_path / "evaluations" / "interrupted.proposal.json"
    request_ids = [
        f"interrupted:{extraction_pass}:{tile.tile_id}"
        for extraction_pass in PASS_ORDER
        for tile in build_tiles(PixelRegion(x=0, y=0, width=100, height=100))
    ]
    first_fixtures = {
        request_id: MockFixture(output={"candidates": [], "warnings": []})
        for request_id in request_ids[:5]
    }
    first_fixtures[request_ids[5]] = MockFixture(scenario="failure")

    with pytest.raises(Exception):
        asyncio.run(
            run_tiled_extraction(
                provider=MockAIProvider(first_fixtures),
                image_path=image_path,
                experiment_id="interrupted",
                benchmark_document_id="benchmark:hydrolysis",
                benchmark_page_id="benchmark:hydrolysis:IMG_6807.JPG",
                roi=PixelRegion(x=0, y=0, width=100, height=100),
                checkpoint_dir=run_dir,
                final_output_path=final_output_path,
            )
        )

    assert [path.name for path in sorted((run_dir / "calls").glob("*.json"))] == [
        "01.json", "02.json", "03.json", "04.json", "05.json"
    ]
    assert not final_output_path.exists()
    resumed_fixtures = {
        request_id: MockFixture(output={"candidates": [], "warnings": []})
        for request_id in request_ids[5:]
    }
    snapshot = asyncio.run(
        run_tiled_extraction(
            provider=MockAIProvider(resumed_fixtures),
            image_path=image_path,
            experiment_id="interrupted",
            benchmark_document_id="benchmark:hydrolysis",
            benchmark_page_id="benchmark:hydrolysis:IMG_6807.JPG",
            roi=PixelRegion(x=0, y=0, width=100, height=100),
            checkpoint_dir=run_dir,
            final_output_path=final_output_path,
        )
    )

    assert len(snapshot.calls) == 12
    assert len(list((run_dir / "calls").glob("*.json"))) == 12
    assert final_output_path.is_file()


def test_resume_rejects_configuration_mismatch_before_provider_call(tmp_path: Path) -> None:
    image_path = tmp_path / "screen.jpg"
    Image.new("RGB", (100, 100), "white").save(image_path, format="JPEG")
    run_dir = tmp_path / "runs" / "mismatch"
    fixtures = {
        f"mismatch:{extraction_pass}:{tile.tile_id}": MockFixture(
            output={"candidates": [], "warnings": []}
        )
        for extraction_pass in PASS_ORDER
        for tile in build_tiles(PixelRegion(x=0, y=0, width=100, height=100))
    }
    asyncio.run(
        run_tiled_extraction(
            provider=MockAIProvider(fixtures), image_path=image_path, experiment_id="mismatch",
            benchmark_document_id="benchmark:hydrolysis",
            benchmark_page_id="benchmark:hydrolysis:IMG_6807.JPG",
            roi=PixelRegion(x=0, y=0, width=100, height=100), checkpoint_dir=run_dir,
        )
    )

    with pytest.raises(ValueError, match="configuration mismatch"):
        asyncio.run(
            run_tiled_extraction(
                provider=MockAIProvider({}), image_path=image_path, experiment_id="mismatch",
                benchmark_document_id="benchmark:hydrolysis",
                benchmark_page_id="benchmark:hydrolysis:IMG_6807.JPG",
                roi=PixelRegion(x=0, y=0, width=100, height=100),
                maximum_output_tokens=5999, checkpoint_dir=run_dir,
            )
        )


def test_checkpoint_files_never_contain_request_images_or_api_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "sk-test-do-not-persist"
    monkeypatch.setenv("AI_API_KEY", secret)
    image_path = tmp_path / "screen.jpg"
    Image.new("RGB", (100, 100), "white").save(image_path, format="JPEG")
    run_dir = tmp_path / "runs" / "no-secrets"
    fixtures = {
        f"no-secrets:{extraction_pass}:{tile.tile_id}": MockFixture(
            output={"candidates": [], "warnings": []}
        )
        for extraction_pass in PASS_ORDER
        for tile in build_tiles(PixelRegion(x=0, y=0, width=100, height=100))
    }

    asyncio.run(
        run_tiled_extraction(
            provider=MockAIProvider(fixtures), image_path=image_path, experiment_id="no-secrets",
            benchmark_document_id="benchmark:hydrolysis",
            benchmark_page_id="benchmark:hydrolysis:IMG_6807.JPG",
            roi=PixelRegion(x=0, y=0, width=100, height=100), checkpoint_dir=run_dir,
        )
    )

    persisted = "".join(path.read_text(encoding="utf-8") for path in run_dir.rglob("*.json"))
    assert secret not in persisted
    assert "image/png;base64" not in persisted
    assert "apiKey" not in persisted


def test_failure_checkpoint_persists_only_safe_provider_diagnostics(tmp_path: Path) -> None:
    class FailingProvider:
        provider_name = "openai"
        model = "configured-model"

        async def extract(self, request, output_type):
            raise ProviderRequestError(
                ProviderFailureMetadata(
                    provider="openai",
                    model=self.model,
                    requestId=request.request_id,
                    responseId="resp_safe",
                    httpStatus=200,
                    responseStatus="incomplete",
                    incompleteDetails={"reason": "max_output_tokens"},
                    terminationReason="max_output_tokens",
                    usage={"inputTokens": 100, "outputTokens": 6000, "totalTokens": 6100},
                    latencyMs=123.5,
                    failureCategory="max_output_tokens_exhausted",
                    structuredParsingBegan=False,
                    candidateValidationBegan=False,
                )
            )

    secret = "sk-never-persist"
    image_path = tmp_path / "screen.jpg"
    Image.new("RGB", (100, 100), "white").save(image_path, format="JPEG")
    run_dir = tmp_path / "runs" / "safe-failure"

    with pytest.raises(ProviderRequestError):
        asyncio.run(
            run_tiled_extraction(
                provider=FailingProvider(),
                image_path=image_path,
                experiment_id="safe-failure",
                benchmark_document_id="benchmark:hydrolysis",
                benchmark_page_id="benchmark:hydrolysis:IMG_6807.JPG",
                roi=PixelRegion(x=0, y=0, width=100, height=100),
                checkpoint_dir=run_dir,
            )
        )

    failure = (run_dir / "failure.json").read_text(encoding="utf-8")
    payload = json.loads(failure)
    assert payload["callNumber"] == 1
    assert payload["extractionPass"] == "equipment_boundary"
    assert payload["tile"]["tileId"] == "r0c0"
    assert payload["providerFailure"]["responseId"] == "resp_safe"
    assert payload["providerFailure"]["failureCategory"] == "max_output_tokens_exhausted"
    assert payload["providerFailure"]["usage"]["outputTokens"] == 6000
    assert secret not in failure
    assert "data:image" not in failure


def test_taxonomy_separates_strict_scope_visual_extras_and_ui() -> None:
    proposal = {
        "candidates": [
            candidate("equipment", kind="equipment"),
            candidate("valve", kind="valve"),
            EntityCandidate.model_validate(
                {
                    "candidateId": "logo",
                    "kind": "text",
                    "displayName": "HollySys logo",
                    "provenance": [{"sourceRef": "tile"}],
                }
            ),
        ],
        "warnings": [],
    }

    result = classify_proposal_taxonomy(EntityExtractionProposal.model_validate(proposal))

    assert result.in_scope_semantic_candidate_ids == ["equipment"]
    assert result.out_of_reference_scope_visual_candidate_ids == ["valve"]
    assert result.obvious_ui_or_non_engineering_candidate_ids == ["logo"]

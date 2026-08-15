from app.ai.entity_proposals import EntityCandidate, EntityExtractionProposal
from app.ai.topology_proposals import TopologyExtractionProposal
from app.domain.models import EngineeringEntity
from app.evaluation.evaluator import (
    ReferenceScope,
    evaluate_img_6807,
    load_img_6807_reference,
    normalize_comparison_text,
)


def reference(
    entity_id: str,
    *,
    kind: str = "equipment",
    tag: str | None = None,
    display_name: str | None = None,
    source_id: str | None = None,
) -> EngineeringEntity:
    properties = {"sourceNodeId": source_id} if source_id else {}
    return EngineeringEntity.model_validate(
        {
            "id": entity_id,
            "documentId": "benchmark:hydrolysis",
            "pageId": "benchmark:hydrolysis:unassigned",
            "kind": kind,
            "tag": tag,
            "displayName": display_name,
            "properties": properties,
            "assertion": {"mode": "observed", "reviewStatus": "needs_source"},
            "provenance": [],
            "createdAt": "1970-01-01T00:00:00Z",
            "updatedAt": "1970-01-01T00:00:00Z",
        }
    )


def candidate(
    candidate_id: str,
    *,
    kind: str = "equipment",
    tag: str | None = None,
    display_name: str | None = None,
    source_id: str | None = None,
    bbox: dict | None = None,
) -> EntityCandidate:
    properties = [{"name": "sourceNodeId", "value": source_id}] if source_id else []
    return EntityCandidate.model_validate(
        {
            "candidateId": candidate_id,
            "kind": kind,
            "tag": tag,
            "displayName": display_name,
            "properties": properties,
            "geometry": {"bbox": bbox} if bbox else None,
            "provenance": [{"sourceRef": "IMG_6807.JPG"}],
        }
    )


def evaluate(candidates, references):
    return evaluate_img_6807(
        proposal=EntityExtractionProposal(candidates=candidates, warnings=[]),
        topology=TopologyExtractionProposal(connections=[], warnings=[]),
        run_id="test-run",
        reference=ReferenceScope(entities=references, connection_count=0, warnings=[]),
    )


def test_exact_tag_matching_uses_only_conservative_normalization() -> None:
    result = evaluate(
        [candidate("c1", tag="  fit_ 0830 ")],
        [reference("r1", tag="FIT_0830")],
    )

    assert normalize_comparison_text("  fit_ 0830 ") == "fit_0830"
    assert result.matches[0].method == "exact_tag"
    assert result.matches[0].candidate_tag == "  fit_ 0830 "
    assert result.matches[0].reference_tag == "FIT_0830"


def test_matching_falls_back_to_source_identifier_then_display_name() -> None:
    result = evaluate(
        [
            candidate("source", source_id="N_A310001A"),
            candidate("name", display_name="  Hydrolysis vessel "),
        ],
        [
            reference("r-source", source_id="n_a310001a"),
            reference("r-name", display_name="hydrolysis vessel"),
        ],
    )

    assert [(match.candidate_id, match.method) for match in result.matches] == [
        ("name", "exact_display_name"),
        ("source", "exact_source_identifier"),
    ]


def test_duplicate_tag_is_ambiguous_and_not_guessed_one_to_one() -> None:
    result = evaluate(
        [candidate("c1", tag="FIT_0830"), candidate("c2", tag="FIT_0830")],
        [reference("r1", tag="FIT_0830")],
    )

    assert result.matches == []
    assert result.unmatched_candidate_ids == ["c1", "c2"]
    assert [ambiguity.reference_ids for ambiguity in result.ambiguous_matches] == [
        ["r1"],
        ["r1"],
    ]


def test_metrics_cover_matches_false_positives_misses_kind_and_instruments() -> None:
    result = evaluate(
        [
            candidate("instrument", kind="instrument", tag="TE_1"),
            candidate("wrong-kind", kind="instrument", tag="V_1"),
            candidate("false-positive", kind="equipment", tag="NO_MATCH"),
        ],
        [
            reference("r-instrument", kind="instrument", tag="TE_1"),
            reference("r-equipment", kind="equipment", tag="V_1"),
            reference("r-missed", kind="boundary", tag="BND_1"),
        ],
    )
    metrics = result.metrics

    assert (metrics.proposed, metrics.matched, metrics.unmatched_candidates) == (3, 2, 1)
    assert metrics.unmatched_references == 1
    assert metrics.semantic_precision.value == 0.666667
    assert metrics.semantic_recall.value == 0.666667
    assert metrics.semantic_f1 == 0.666667
    assert metrics.exact_tag_accuracy.value == 1
    assert metrics.kind_accuracy.value == 0.5
    assert metrics.instrument_precision.value == 0.5
    assert metrics.instrument_recall.value == 1
    assert result.unmatched_candidate_ids == ["false-positive"]
    assert result.unmatched_reference_ids == ["r-missed"]


def test_geometry_is_coverage_validity_only_and_zero_topology_is_valid() -> None:
    result = evaluate(
        [
            candidate("valid", bbox={"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}),
            candidate("degenerate", bbox={"x": 0.5, "y": 0.5, "width": 0, "height": 0.2}),
            candidate("missing"),
        ],
        [],
    )
    dumped = result.model_dump(mode="json", by_alias=True)

    assert result.geometry.label == "geometry proposal coverage/validity"
    assert result.geometry.candidates_with_bbox == 2
    assert result.geometry.candidates_without_bbox == 1
    assert result.geometry.bbox_values_within_normalized_range == 2
    assert result.geometry.malformed_or_degenerate_bbox == 1
    assert result.geometry.geometry_accuracy_scored is False
    assert all("iou" not in key.casefold() for key in dumped["geometry"])
    assert result.topology.proposal_count == 0
    assert result.topology.semantic_scoring_status == "not_scored_no_proposals"
    assert result.topology.connection_geometry_scored is False


def test_actual_page_reference_scope_and_repeated_evaluation_are_deterministic() -> None:
    scope = load_img_6807_reference()
    proposal = EntityExtractionProposal(
        candidates=[candidate("known", kind="instrument", tag="TE_0807A")], warnings=[]
    )

    first = evaluate_img_6807(proposal=proposal, run_id="repeat", reference=scope)
    second = evaluate_img_6807(proposal=proposal, run_id="repeat", reference=scope)

    assert len(scope.entities) == 64
    assert sum(entity.kind == "instrument" for entity in scope.entities) == 43
    assert scope.connection_count == 85
    assert first.model_dump_json(by_alias=True) == second.model_dump_json(by_alias=True)

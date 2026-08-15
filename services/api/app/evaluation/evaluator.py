from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from app.ai.entity_proposals import EntityCandidate, EntityExtractionProposal
from app.ai.topology_proposals import TopologyExtractionProposal
from app.domain.models import EngineeringEntity, EngineeringGraph
from app.evaluation.schemas import (
    AmbiguousMatch,
    BenchmarkIdentity,
    EntityEvaluationResult,
    EntityMatch,
    EntityMetrics,
    EvaluationProviderMetadata,
    GeometryProposalDiagnostics,
    RatioMetric,
    TopologyDiagnostics,
)

ROOT = Path(__file__).parents[4]
DEFAULT_GRAPH_PATH = ROOT / "benchmarks/hydrolysis/expected/engineering_graph.json"
DEFAULT_PAGE_PATH = ROOT / "benchmarks/hydrolysis/expected/pages/IMG_6807.page.json"
SOURCE_IDENTIFIER_NAMES = {
    "dcsid",
    "dcstag",
    "sourceid",
    "sourcenodeid",
    "sourceinstrumentid",
    "instrumentid",
}
MATCH_METHODS = ("exact_tag", "exact_source_identifier", "exact_display_name")


@dataclass(frozen=True)
class ReferenceScope:
    entities: list[EngineeringEntity]
    connection_count: int
    warnings: list[str]


def normalize_comparison_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s*([_-])\s*", r"\1", value.strip().casefold())
    return normalized or None


def load_img_6807_reference(
    graph_path: Path = DEFAULT_GRAPH_PATH, page_path: Path = DEFAULT_PAGE_PATH
) -> ReferenceScope:
    graph = EngineeringGraph.model_validate_json(graph_path.read_text(encoding="utf-8"))
    page = json.loads(page_path.read_text(encoding="utf-8"))
    entity_ids = set(page["linkedEntityIds"])
    entities = sorted(
        (entity for entity in graph.entities if entity.id in entity_ids), key=lambda item: item.id
    )
    if len(entities) != page["counts"]["entities"]:
        raise ValueError("page fixture entity IDs do not resolve exactly in EngineeringGraph")
    if page["geometryCoverage"]["entitiesWithVerifiedGeometry"] != 0:
        raise ValueError("IMG_6807 evaluator requires zero verified reference geometry")
    return ReferenceScope(
        entities=entities,
        connection_count=page["counts"]["connections"],
        warnings=list(page.get("warnings", [])),
    )


def evaluate_img_6807(
    *,
    proposal: EntityExtractionProposal,
    topology: TopologyExtractionProposal | None = None,
    run_id: str,
    provider_metadata: EvaluationProviderMetadata | None = None,
    reference: ReferenceScope | None = None,
) -> EntityEvaluationResult:
    scope = reference or load_img_6807_reference()
    candidates = sorted(proposal.candidates, key=lambda item: item.candidate_id)
    candidate_id_counts = Counter(candidate.candidate_id for candidate in candidates)
    duplicate_candidate_ids = sorted(
        candidate_id for candidate_id, count in candidate_id_counts.items() if count > 1
    )
    if duplicate_candidate_ids:
        raise ValueError("proposal contains duplicate candidate IDs: " + ", ".join(duplicate_candidate_ids))
    references = scope.entities
    matches, ambiguities = _match_candidates(candidates, references)
    matched_candidate_ids = {match.candidate_id for match in matches}
    matched_reference_ids = {match.reference_id for match in matches}
    unmatched_candidates = [
        candidate.candidate_id
        for candidate in candidates
        if candidate.candidate_id not in matched_candidate_ids
    ]
    unmatched_references = [
        reference.id for reference in references if reference.id not in matched_reference_ids
    ]
    topology_count = len(topology.connections) if topology is not None else 0
    warnings = [*scope.warnings, *proposal.warnings]
    if topology is not None:
        warnings.extend(topology.warnings)
    if ambiguities:
        warnings.append(f"{len(ambiguities)} candidate match(es) remain ambiguous and unscored")
    return EntityEvaluationResult(
        benchmark=BenchmarkIdentity(),
        run_id=run_id,
        provider_metadata=provider_metadata,
        metrics=_metrics(candidates, references, matches),
        matches=matches,
        unmatched_candidate_ids=unmatched_candidates,
        unmatched_reference_ids=unmatched_references,
        ambiguous_matches=ambiguities,
        geometry=_geometry_diagnostics(candidates),
        topology=TopologyDiagnostics(
            proposal_count=topology_count,
            reference_connection_count=scope.connection_count,
            semantic_scoring_status=(
                "not_scored_no_proposals"
                if topology_count == 0
                else "limited_requires_unambiguous_entity_matches"
            ),
        ),
        warnings=warnings,
        limitations=[
            "Reference membership is semantic provenance support for IMG_6807.JPG, not certified P&ID truth.",
            "No verified entity geometry exists; bbox/IoU/localization accuracy is not scored.",
            "No verified connection geometry exists; connection path accuracy is not scored.",
            "Topology semantics may be compared only after both proposal endpoints match reference entities unambiguously.",
        ],
    )


def _match_candidates(
    candidates: list[EntityCandidate], references: list[EngineeringEntity]
) -> tuple[list[EntityMatch], list[AmbiguousMatch]]:
    unmatched_candidates = {candidate.candidate_id: candidate for candidate in candidates}
    unmatched_references = {reference.id: reference for reference in references}
    matches: list[EntityMatch] = []
    for method in MATCH_METHODS:
        options = _options(unmatched_candidates.values(), unmatched_references.values(), method)
        reverse: dict[str, list[str]] = defaultdict(list)
        for candidate_id, reference_ids in options.items():
            for reference_id in reference_ids:
                reverse[reference_id].append(candidate_id)
        pairs = sorted(
            (candidate_id, reference_ids[0])
            for candidate_id, reference_ids in options.items()
            if len(reference_ids) == 1 and len(reverse[reference_ids[0]]) == 1
        )
        for candidate_id, reference_id in pairs:
            candidate = unmatched_candidates.pop(candidate_id)
            reference = unmatched_references.pop(reference_id)
            matches.append(
                EntityMatch(
                    candidate_id=candidate_id,
                    reference_id=reference_id,
                    method=method,
                    candidate_tag=candidate.tag,
                    reference_tag=reference.tag,
                    candidate_kind=candidate.kind,
                    reference_kind=reference.kind,
                )
            )
    ambiguities: list[AmbiguousMatch] = []
    for candidate in unmatched_candidates.values():
        for method in MATCH_METHODS:
            reference_ids = _matching_reference_ids(candidate, unmatched_references.values(), method)
            if reference_ids:
                ambiguities.append(
                    AmbiguousMatch(
                        candidate_id=candidate.candidate_id,
                        method=method,
                        candidate_value=_candidate_values(candidate, method)[0],
                        reference_ids=reference_ids,
                    )
                )
                break
    return sorted(matches, key=lambda item: item.candidate_id), sorted(
        ambiguities, key=lambda item: item.candidate_id
    )


def _options(candidates, references, method: str) -> dict[str, list[str]]:
    reference_list = list(references)
    return {
        candidate.candidate_id: ids
        for candidate in candidates
        if (ids := _matching_reference_ids(candidate, reference_list, method))
    }


def _matching_reference_ids(
    candidate: EntityCandidate, references, method: str
) -> list[str]:
    candidate_values = set(_candidate_values(candidate, method))
    if not candidate_values:
        return []
    return sorted(
        reference.id
        for reference in references
        if candidate_values.intersection(_reference_values(reference, method))
    )


def _candidate_values(candidate: EntityCandidate, method: str) -> list[str]:
    if method == "exact_tag":
        value = normalize_comparison_text(candidate.tag)
        return [value] if value else []
    if method == "exact_display_name":
        value = normalize_comparison_text(candidate.display_name)
        return [value] if value else []
    return sorted(
        {
            normalized
            for item in candidate.properties
            if item.name.replace("_", "").casefold() in SOURCE_IDENTIFIER_NAMES
            if (normalized := normalize_comparison_text(str(item.value)))
        }
    )


def _reference_values(reference: EngineeringEntity, method: str) -> set[str]:
    if method == "exact_tag":
        value = normalize_comparison_text(reference.tag)
        return {value} if value else set()
    if method == "exact_display_name":
        value = normalize_comparison_text(reference.display_name)
        return {value} if value else set()
    values = set()
    for name, raw_value in reference.properties.items():
        if name.replace("_", "").casefold() in SOURCE_IDENTIFIER_NAMES and isinstance(
            raw_value, (str, int, float)
        ):
            if normalized := normalize_comparison_text(str(raw_value)):
                values.add(normalized)
    return values


def _ratio(numerator: int, denominator: int) -> RatioMetric:
    return RatioMetric(
        numerator=numerator,
        denominator=denominator,
        value=round(numerator / denominator, 6) if denominator else 0,
    )


def _metrics(
    candidates: list[EntityCandidate],
    references: list[EngineeringEntity],
    matches: list[EntityMatch],
) -> EntityMetrics:
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    reference_by_id = {reference.id: reference for reference in references}
    tagged_matches = [
        match for match in matches if match.candidate_tag is not None and match.reference_tag is not None
    ]
    exact_tags = sum(
        normalize_comparison_text(match.candidate_tag)
        == normalize_comparison_text(match.reference_tag)
        for match in tagged_matches
    )
    correct_kind = sum(match.candidate_kind == match.reference_kind for match in matches)
    instrument_candidates = [candidate for candidate in candidates if candidate.kind == "instrument"]
    instrument_references = [reference for reference in references if reference.kind == "instrument"]
    correct_instruments = sum(
        candidate_by_id[match.candidate_id].kind == "instrument"
        and reference_by_id[match.reference_id].kind == "instrument"
        for match in matches
    )
    precision = _ratio(len(matches), len(candidates))
    recall = _ratio(len(matches), len(references))
    f1 = (
        round(2 * precision.value * recall.value / (precision.value + recall.value), 6)
        if precision.value + recall.value
        else 0
    )
    proposed_by_kind = Counter(candidate.kind for candidate in candidates)
    reference_by_kind = Counter(reference.kind for reference in references)
    correct_by_kind = Counter(
        match.reference_kind for match in matches if match.candidate_kind == match.reference_kind
    )
    return EntityMetrics(
        proposed=len(candidates),
        references=len(references),
        matched=len(matches),
        unmatched_candidates=len(candidates) - len(matches),
        unmatched_references=len(references) - len(matches),
        semantic_precision=precision,
        semantic_recall=recall,
        semantic_f1=f1,
        exact_tag_accuracy=_ratio(exact_tags, len(tagged_matches)),
        kind_accuracy=_ratio(correct_kind, len(matches)),
        instrument_precision=_ratio(correct_instruments, len(instrument_candidates)),
        instrument_recall=_ratio(correct_instruments, len(instrument_references)),
        proposed_by_kind=dict(sorted(proposed_by_kind.items())),
        reference_by_kind=dict(sorted(reference_by_kind.items())),
        matched_correct_kind_by_kind=dict(sorted(correct_by_kind.items())),
    )


def _geometry_diagnostics(candidates: list[EntityCandidate]) -> GeometryProposalDiagnostics:
    boxes = [candidate.geometry.bbox for candidate in candidates if candidate.geometry and candidate.geometry.bbox]
    degenerate = sum(box.width <= 0 or box.height <= 0 for box in boxes)
    return GeometryProposalDiagnostics(
        candidates_with_bbox=len(boxes),
        candidates_without_bbox=len(candidates) - len(boxes),
        bbox_values_within_normalized_range=len(boxes),
        malformed_or_degenerate_bbox=degenerate,
    )


def render_summary(result: EntityEvaluationResult, *, examples: int = 3) -> str:
    metrics = result.metrics
    lines = [
        f"Benchmark: {result.benchmark.source_filename} ({result.run_id})",
        f"Entities: {metrics.matched}/{metrics.proposed} proposals matched; "
        f"{metrics.unmatched_references}/{metrics.references} references missed",
        f"Precision={metrics.semantic_precision.value:.3f} "
        f"Recall={metrics.semantic_recall.value:.3f} F1={metrics.semantic_f1:.3f}",
        f"Geometry proposal coverage: {result.geometry.candidates_with_bbox}/{metrics.proposed} "
        "with bbox; geometry accuracy not scored",
        f"Topology proposals: {result.topology.proposal_count}; connection geometry not scored",
        "Matched examples: " + ", ".join(match.candidate_id for match in result.matches[:examples]),
        "False-positive proposal examples: "
        + ", ".join(result.unmatched_candidate_ids[:examples]),
        "Missed reference examples: " + ", ".join(result.unmatched_reference_ids[:examples]),
        "Ambiguous examples: "
        + ", ".join(match.candidate_id for match in result.ambiguous_matches[:examples]),
    ]
    return "\n".join(lines)

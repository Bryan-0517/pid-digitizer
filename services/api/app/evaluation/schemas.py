from typing import Literal

from pydantic import Field

from app.ai.contracts import AIContract, TokenUsage
from app.digitization.schemas import DigitizationProposalResponse


class EvaluationProviderMetadata(AIContract):
    provider: str | None = None
    model: str | None = None
    request_id: str | None = None
    latency_ms: float | None = Field(default=None, ge=0)
    usage: TokenUsage | None = None


class EntityMatch(AIContract):
    candidate_id: str
    reference_id: str
    method: Literal["exact_tag", "exact_source_identifier", "exact_display_name"]
    candidate_tag: str | None = None
    reference_tag: str | None = None
    candidate_kind: str
    reference_kind: str


class AmbiguousMatch(AIContract):
    candidate_id: str
    method: Literal["exact_tag", "exact_source_identifier", "exact_display_name"]
    candidate_value: str
    reference_ids: list[str]


class RatioMetric(AIContract):
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    value: float = Field(ge=0, le=1)


class EntityMetrics(AIContract):
    proposed: int
    references: int
    matched: int
    unmatched_candidates: int
    unmatched_references: int
    semantic_precision: RatioMetric
    semantic_recall: RatioMetric
    semantic_f1: float = Field(ge=0, le=1)
    exact_tag_accuracy: RatioMetric
    kind_accuracy: RatioMetric
    instrument_precision: RatioMetric
    instrument_recall: RatioMetric
    proposed_by_kind: dict[str, int]
    reference_by_kind: dict[str, int]
    matched_correct_kind_by_kind: dict[str, int]


class GeometryProposalDiagnostics(AIContract):
    label: Literal["geometry proposal coverage/validity"] = "geometry proposal coverage/validity"
    candidates_with_bbox: int
    candidates_without_bbox: int
    bbox_values_within_normalized_range: int
    malformed_or_degenerate_bbox: int
    verified_reference_geometry: int = 0
    geometry_accuracy_scored: bool = False


class TopologyDiagnostics(AIContract):
    proposal_count: int
    reference_connection_count: int
    connection_geometry_scored: bool = False
    semantic_scoring_status: Literal[
        "not_scored_no_proposals", "limited_requires_unambiguous_entity_matches"
    ]


class BenchmarkIdentity(AIContract):
    name: Literal["hydrolysis"] = "hydrolysis"
    document_id: str = "benchmark:hydrolysis"
    page_id: str = "benchmark:hydrolysis:IMG_6807.JPG"
    source_filename: str = "IMG_6807.JPG"


class LiveProposalSnapshot(AIContract):
    snapshot_label: Literal["MODEL OUTPUT SNAPSHOT — NOT BENCHMARK TRUTH"] = (
        "MODEL OUTPUT SNAPSHOT — NOT BENCHMARK TRUTH"
    )
    benchmark: BenchmarkIdentity = Field(default_factory=BenchmarkIdentity)
    captured_proposal: DigitizationProposalResponse


class EntityEvaluationResult(AIContract):
    schema_version: Literal["0.1"] = "0.1"
    benchmark: BenchmarkIdentity = Field(default_factory=BenchmarkIdentity)
    run_id: str
    provider_metadata: EvaluationProviderMetadata | None = None
    metrics: EntityMetrics
    matches: list[EntityMatch]
    unmatched_candidate_ids: list[str]
    unmatched_reference_ids: list[str]
    ambiguous_matches: list[AmbiguousMatch]
    geometry: GeometryProposalDiagnostics
    topology: TopologyDiagnostics
    warnings: list[str]
    limitations: list[str]

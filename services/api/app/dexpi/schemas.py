from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.domain.models import Assertion, DomainModel, JsonValue


FieldDisposition = Literal["supported", "unmapped", "blocked"]
ObjectDisposition = Literal["supported", "partial", "unmapped", "blocked"]
GraphStatus = Literal["supported", "partial", "blocked", "empty"]


class FieldReport(DomainModel):
    path: str
    disposition: FieldDisposition
    reason_code: str
    message: str
    value: JsonValue = None


class ObjectReport(DomainModel):
    object_type: Literal["entity", "connection"]
    canonical_id: str
    kind: str
    label: str | None = None
    disposition: ObjectDisposition
    assertion: Assertion | None = None
    suggested_class: str | None = None
    original_mapping_status: str | None = None
    fields: list[FieldReport]


class MappingCounts(DomainModel):
    supported_objects: int = 0
    partial_objects: int = 0
    unmapped_objects: int = 0
    blocked_objects: int = 0
    supported_fields: int = 0
    unmapped_fields: int = 0
    blocked_fields: int = 0


class PreviewObject(DomainModel):
    object_type: Literal["entity", "connection"]
    canonical_id: str
    kind: str
    supported_fields: dict[str, JsonValue]


class DexpiMappingPreview(DomainModel):
    boundary_version: Literal["internal-v0.1"] = "internal-v0.1"
    target_dexpi_version: None = None
    conformant: Literal[False] = False
    objects: list[PreviewObject] = Field(default_factory=list)


class DexpiMappingReport(DomainModel):
    boundary_version: Literal["internal-v0.1"] = "internal-v0.1"
    target_dexpi_version: None = None
    conformance_validated: Literal[False] = False
    status: GraphStatus
    graph_fields: list[FieldReport]
    objects: list[ObjectReport]
    counts: MappingCounts
    preview: DexpiMappingPreview
    warnings: list[str] = Field(default_factory=lambda: [
        "Version-neutral preflight only; this report is not DEXPI conformance certification."
    ])

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.domain.models import DomainModel


class ExportAvailability(DomainModel):
    enabled: bool
    available: bool
    pydexpi_version: Literal["1.2.0"] = "1.2.0"
    target_dexpi_version: Literal["1.3"] = "1.3"
    artifact_label: str = "pyDEXPI 1.2.0 / DEXPI 1.3 compatibility JSON"
    reason: str | None = None


class IncludedObject(DomainModel):
    canonical_id: str
    canonical_kind: str
    pydexpi_class: str
    converted_field_paths: list[str]


class OmittedObject(DomainModel):
    canonical_id: str
    object_type: Literal["entity", "connection"]
    canonical_kind: str
    t015_disposition: str
    reason_code: str
    message: str


class OmittedField(DomainModel):
    canonical_id: str
    path: str
    reason_code: str
    message: str


class BlockingObject(DomainModel):
    canonical_id: str
    reason_codes: list[str]


class ConversionReport(DomainModel):
    status: Literal["ready", "blocked", "empty", "no_exportable_content"]
    pydexpi_version: Literal["1.2.0"] = "1.2.0"
    target_dexpi_version: Literal["1.3"] = "1.3"
    conformance_validated: Literal[False] = False
    artifact_label: str = "pyDEXPI 1.2.0 / DEXPI 1.3 compatibility JSON"
    included_objects: list[IncludedObject] = Field(default_factory=list)
    omitted_objects: list[OmittedObject] = Field(default_factory=list)
    omitted_fields: list[OmittedField] = Field(default_factory=list)
    blocking_objects: list[BlockingObject] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

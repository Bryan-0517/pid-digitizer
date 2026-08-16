from __future__ import annotations

import importlib.metadata
import json
from dataclasses import dataclass
from typing import Any

from app.dexpi.export_schemas import (
    BlockingObject,
    ConversionReport,
    IncludedObject,
    OmittedField,
    OmittedObject,
)
from app.dexpi.schemas import DexpiMappingReport, ObjectReport
from app.domain.models import EngineeringEntity, EngineeringGraph


PYDEXPI_VERSION = "1.2.0"
TARGET_DEXPI_VERSION = "1.3"
ARTIFACT_LABEL = "pyDEXPI 1.2.0 / DEXPI 1.3 compatibility JSON"

_MAPPING_HINTS = {
    "centrifugal_pump": "CentrifugalPump",
    "tank": "Tank",
}
_SUGGESTED_CLASS_ALLOWLIST = {"CentrifugalPump", "Tank"}
_CONVERTED_FIELDS = frozenset({"id", "kind", "tag"})


class PydexpiCompatibilityError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExportArtifact:
    content: bytes
    report: ConversionReport


def installed_pydexpi_version() -> str | None:
    try:
        return importlib.metadata.version("pydexpi")
    except importlib.metadata.PackageNotFoundError:
        return None


def package_is_compatible() -> bool:
    return installed_pydexpi_version() == PYDEXPI_VERSION


class PydexpiV12Adapter:
    """Lazy, version-specific compatibility adapter isolated from canonical modules."""

    def plan(
        self, graph: EngineeringGraph, preflight: DexpiMappingReport
    ) -> ConversionReport:
        if preflight.status == "empty":
            return ConversionReport(
                status="empty",
                warnings=["The canonical graph contains no exportable content."],
            )
        blocked = [item for item in preflight.objects if item.disposition == "blocked"]
        if blocked:
            return ConversionReport(
                status="blocked",
                blocking_objects=[
                    BlockingObject(
                        canonical_id=item.canonical_id,
                        reason_codes=sorted({
                            field.reason_code
                            for field in item.fields
                            if field.disposition == "blocked"
                        }),
                    )
                    for item in blocked
                ],
                warnings=["Blocked canonical objects prevent whole-document export."],
            )

        reports = {item.canonical_id: item for item in preflight.objects}
        included: list[IncludedObject] = []
        omitted_objects: list[OmittedObject] = []
        omitted_fields: list[OmittedField] = []
        for entity in sorted(graph.entities, key=lambda item: item.id):
            item_report = reports[entity.id]
            class_name, reason = self._mapping_class(entity)
            if item_report.disposition == "unmapped" or class_name is None:
                reason_code = (
                    "t015_unmapped_object"
                    if item_report.disposition == "unmapped"
                    else reason or "no_exact_t016_mapping"
                )
                omitted_objects.append(OmittedObject(
                    canonical_id=entity.id,
                    object_type="entity",
                    canonical_kind=str(entity.kind),
                    t015_disposition=item_report.disposition,
                    reason_code=reason_code,
                    message="No approved exact pyDEXPI mapping was constructed.",
                ))
                omitted_fields.extend(self._all_fields_omitted(item_report, reason_code))
                continue
            included.append(IncludedObject(
                canonical_id=entity.id,
                canonical_kind=str(entity.kind),
                pydexpi_class=class_name,
                converted_field_paths=sorted(_CONVERTED_FIELDS),
            ))
            omitted_fields.extend(
                OmittedField(
                    canonical_id=entity.id,
                    path=field.path,
                    reason_code=(
                        field.reason_code
                        if field.disposition == "unmapped"
                        else "not_in_t016_tiny_mapping"
                    ),
                    message="Canonical field was not converted by the tiny compatibility mapping.",
                )
                for field in item_report.fields
                if field.path not in _CONVERTED_FIELDS
            )

        for connection in sorted(graph.connections, key=lambda item: item.id):
            item_report = reports[connection.id]
            omitted_objects.append(OmittedObject(
                canonical_id=connection.id,
                object_type="connection",
                canonical_kind=str(connection.kind),
                t015_disposition=item_report.disposition,
                reason_code="connection_mapping_not_in_t016_subset",
                message="Connections are outside the approved entity-only T016 spike.",
            ))
            omitted_fields.extend(self._all_fields_omitted(
                item_report, "connection_mapping_not_in_t016_subset"
            ))

        status = "ready" if included else "no_exportable_content"
        warnings = [
            "Compatibility JSON is not a standard DEXPI exchange file or conformance certification.",
            "Canonical connections and geometry are not converted by this entity-only spike.",
        ]
        return ConversionReport(
            status=status,
            included_objects=included,
            omitted_objects=omitted_objects,
            omitted_fields=sorted(
                omitted_fields, key=lambda item: (item.canonical_id, item.path)
            ),
            warnings=warnings,
        )

    def export(self, graph: EngineeringGraph, report: ConversionReport) -> ExportArtifact:
        if report.status != "ready":
            raise PydexpiCompatibilityError(f"conversion report is not export-ready: {report.status}")
        if not package_is_compatible():
            raise PydexpiCompatibilityError(
                f"pydexpi=={PYDEXPI_VERSION} is required; found {installed_pydexpi_version()}"
            )
        try:
            public_api = self._load_public_api()
            entities = {entity.id: entity for entity in graph.entities}
            mapped = [
                public_api[item.pydexpi_class](
                    id=item.canonical_id,
                    tagName=entities[item.canonical_id].tag,
                )
                for item in report.included_objects
            ]
            conceptual = public_api["ConceptualModel"](
                id=f"conceptual-{graph.document_id}", taggedPlantItems=mapped
            )
            model = public_api["DexpiModel"](
                id=f"model-{graph.document_id}",
                conceptualModel=conceptual,
                originatingSystemName="P&ID Digitizer T016 compatibility spike",
                originatingSystemVersion="0.1",
            )
            serializer = public_api["JsonSerializer"]()
            model_bytes = serializer.export_to_bytes(model, indent=2)
            serializer.load_from_bytes(model_bytes)
            model_json = json.loads(model_bytes)
        except Exception as exc:
            raise PydexpiCompatibilityError("public pyDEXPI construction or JSON serialization failed") from exc
        envelope = {
            "artifactLabel": ARTIFACT_LABEL,
            "conformanceValidated": False,
            "conversionReport": report.model_dump(by_alias=True),
            "pydexpiModel": model_json,
            "pydexpiVersion": PYDEXPI_VERSION,
            "targetDexpiVersion": TARGET_DEXPI_VERSION,
        }
        content = (json.dumps(envelope, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
        return ExportArtifact(content=content, report=report)

    @staticmethod
    def _mapping_class(entity: EngineeringEntity) -> tuple[str | None, str | None]:
        if entity.kind != "equipment":
            return None, "no_exact_t016_mapping"
        hints: set[str] = set()
        subtype = (entity.subtype or "").strip().lower()
        if subtype in _MAPPING_HINTS:
            hints.add(_MAPPING_HINTS[subtype])
        suggested = entity.dexpi.suggested_class if entity.dexpi else None
        if suggested in _SUGGESTED_CLASS_ALLOWLIST:
            hints.add(suggested)
        if len(hints) > 1:
            return None, "conflicting_exact_mapping_hints"
        if not hints:
            return None, "no_exact_t016_mapping"
        return next(iter(hints)), None

    @staticmethod
    def _all_fields_omitted(item: ObjectReport, reason: str) -> list[OmittedField]:
        return [
            OmittedField(
                canonical_id=item.canonical_id,
                path=field.path,
                reason_code=reason,
                message="Object was not constructed in the T016 compatibility model.",
            )
            for field in item.fields
        ]

    @staticmethod
    def _load_public_api() -> dict[str, Any]:
        # Imports stay inside the enabled export path so T015 and API startup remain independent.
        from pydexpi.dexpi_classes.dexpiModel import ConceptualModel, DexpiModel
        from pydexpi.dexpi_classes.equipment import CentrifugalPump, Tank
        from pydexpi.loaders import JsonSerializer

        return {
            "CentrifugalPump": CentrifugalPump,
            "ConceptualModel": ConceptualModel,
            "DexpiModel": DexpiModel,
            "JsonSerializer": JsonSerializer,
            "Tank": Tank,
        }

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.dexpi.schemas import (
    DexpiMappingPreview,
    DexpiMappingReport,
    FieldReport,
    MappingCounts,
    ObjectReport,
    PreviewObject,
)
from app.domain.models import EngineeringConnection, EngineeringEntity, EngineeringGraph


SUPPORTED_ENTITY_KINDS = frozenset({"equipment", "valve", "instrument", "boundary"})
TAG_REQUIRED_ENTITY_KINDS = frozenset({"equipment", "valve", "instrument"})
SUPPORTED_CONNECTION_KINDS = frozenset({"process", "utility", "signal"})
ELIGIBLE_REVIEW_STATUSES = frozenset({"confirmed", "corrected"})


class VersionNeutralDexpiAdapter:
    """Internal preflight only: it neither creates nor validates real DEXPI objects."""

    def validate_mappable(self, graph: EngineeringGraph) -> DexpiMappingReport:
        graph_fields = self._graph_fields(graph)
        known_entities = {entity.id for entity in graph.entities}
        objects = [
            *[self._entity_report(entity) for entity in sorted(graph.entities, key=lambda x: x.id)],
            *[
                self._connection_report(connection, known_entities)
                for connection in sorted(graph.connections, key=lambda x: x.id)
            ],
        ]
        counts = self._counts(graph_fields, objects)
        if not objects:
            status = "empty"
        elif counts.blocked_objects:
            status = "blocked"
        elif counts.partial_objects or counts.unmapped_objects or counts.unmapped_fields:
            status = "partial"
        else:
            status = "supported"
        preview = self._preview(objects)
        return DexpiMappingReport(
            status=status,
            graph_fields=graph_fields,
            objects=objects,
            counts=counts,
            preview=preview,
        )

    def map_supported(self, graph: EngineeringGraph) -> DexpiMappingPreview:
        return self.validate_mappable(graph).preview

    def _entity_report(self, entity: EngineeringEntity) -> ObjectReport:
        kind = str(entity.kind)
        data = entity.model_dump(by_alias=True, exclude_none=True)
        supported_kind = kind in SUPPORTED_ENTITY_KINDS
        fields = self._account_fields(
            data,
            classify=(
                self._entity_field_disposition
                if supported_kind
                else lambda _: self._unmapped("unmapped_entity_kind", kind)
            ),
        )
        if supported_kind:
            blockers = self._eligibility_blockers(entity.assertion.mode, entity.assertion.review_status)
            if kind in TAG_REQUIRED_ENTITY_KINDS and not (entity.tag or "").strip():
                blockers.append(("tag", "blocked_missing_required_tag", "Required canonical tag is missing."))
            fields = self._apply_blockers(fields, blockers)
            disposition = self._eligible_disposition(fields, blockers)
        else:
            disposition = "unmapped"
        return ObjectReport(
            object_type="entity",
            canonical_id=entity.id,
            kind=kind,
            label=entity.tag or entity.display_name,
            disposition=disposition,
            assertion=entity.assertion,
            suggested_class=entity.dexpi.suggested_class if entity.dexpi else None,
            original_mapping_status=entity.dexpi.mapping_status if entity.dexpi else None,
            fields=fields,
        )

    def _connection_report(
        self, connection: EngineeringConnection, known_entities: set[str]
    ) -> ObjectReport:
        kind = str(connection.kind)
        data = connection.model_dump(by_alias=True, exclude_none=True)
        # Direction is optional but must remain explicit in preflight, including an absent value.
        data.setdefault("direction", None)
        supported_kind = kind in SUPPORTED_CONNECTION_KINDS
        fields = self._account_fields(
            data,
            classify=(
                self._connection_field_disposition
                if supported_kind
                else lambda _: self._unmapped("unmapped_connection_kind", kind)
            ),
        )
        if supported_kind:
            blockers = self._eligibility_blockers(
                connection.assertion.mode, connection.assertion.review_status
            )
            source_id = getattr(connection, "source_entity_id", None)
            target_id = getattr(connection, "target_entity_id", None)
            if not source_id:
                blockers.append((
                    "sourceEntityId", "blocked_missing_required_source",
                    "Required canonical source entity ID is missing.",
                ))
            elif source_id not in known_entities:
                blockers.append((
                    "sourceEntityId", "blocked_unresolved_source",
                    "Canonical source entity ID does not resolve in this graph.",
                ))
            if not target_id:
                blockers.append((
                    "targetEntityId", "blocked_missing_required_target",
                    "Required canonical target entity ID is missing.",
                ))
            elif target_id not in known_entities:
                blockers.append((
                    "targetEntityId", "blocked_unresolved_target",
                    "Canonical target entity ID does not resolve in this graph.",
                ))
            fields = self._apply_blockers(fields, blockers)
            disposition = self._eligible_disposition(fields, blockers)
        else:
            disposition = "unmapped"
        return ObjectReport(
            object_type="connection",
            canonical_id=connection.id,
            kind=kind,
            disposition=disposition,
            assertion=connection.assertion,
            fields=fields,
        )

    @staticmethod
    def _entity_field_disposition(path: str) -> tuple[str, str, str]:
        if path.startswith("properties."):
            return VersionNeutralDexpiAdapter._unmapped("unmapped_arbitrary_property", path)
        if path == "geometry" or path.startswith("geometry."):
            return VersionNeutralDexpiAdapter._unmapped("unmapped_geometry", path)
        if path == "dexpi" or path.startswith("dexpi."):
            return VersionNeutralDexpiAdapter._unmapped("unmapped_advisory_dexpi_metadata", path)
        return "supported", "supported_internal_v01", "Eligible for the internal v0.1 boundary."

    @staticmethod
    def _connection_field_disposition(path: str) -> tuple[str, str, str]:
        if path.startswith("properties."):
            return VersionNeutralDexpiAdapter._unmapped("unmapped_arbitrary_property", path)
        if path == "geometry" or path.startswith("geometry."):
            return VersionNeutralDexpiAdapter._unmapped("unmapped_geometry", path)
        return "supported", "supported_internal_v01", "Eligible for the internal v0.1 boundary."

    @staticmethod
    def _unmapped(reason: str, context: str) -> tuple[str, str, str]:
        return "unmapped", reason, f"Preserved canonical content is outside v0.1 mapping: {context}."

    @staticmethod
    def _eligibility_blockers(mode: str, review_status: str) -> list[tuple[str, str, str]]:
        blockers: list[tuple[str, str, str]] = []
        if mode == "inferred":
            blockers.append((
                "assertion.mode", "blocked_inferred_assertion",
                "Inferred canonical objects are not mapping-eligible.",
            ))
        if review_status not in ELIGIBLE_REVIEW_STATUSES:
            blockers.append((
                "assertion.reviewStatus", f"blocked_review_{review_status}",
                f"Review status '{review_status}' is not mapping-eligible.",
            ))
        return blockers

    @staticmethod
    def _apply_blockers(
        fields: list[FieldReport], blockers: list[tuple[str, str, str]]
    ) -> list[FieldReport]:
        by_path = {field.path: field for field in fields}
        for path, reason, message in blockers:
            value = by_path[path].value if path in by_path else None
            by_path[path] = FieldReport(
                path=path, disposition="blocked", reason_code=reason, message=message, value=value
            )
        return sorted(by_path.values(), key=lambda field: field.path)

    @staticmethod
    def _eligible_disposition(
        fields: list[FieldReport], blockers: list[tuple[str, str, str]]
    ) -> str:
        if blockers:
            return "blocked"
        if any(field.disposition == "unmapped" for field in fields):
            return "partial"
        return "supported"

    def _graph_fields(self, graph: EngineeringGraph) -> list[FieldReport]:
        data = graph.model_dump(by_alias=True, exclude_none=True, exclude={"entities", "connections"})

        def classify(path: str) -> tuple[str, str, str]:
            if path.startswith("metadata."):
                return self._unmapped("unmapped_graph_metadata", path)
            return "supported", "supported_internal_v01", "Internal preflight context."

        return self._account_fields(data, classify)

    @staticmethod
    def _account_fields(
        data: dict[str, Any],
        classify: Callable[[str], tuple[str, str, str]],
    ) -> list[FieldReport]:
        fields: list[FieldReport] = []

        def visit(value: Any, path: str) -> None:
            disposition, reason, message = classify(path)
            fields.append(FieldReport(
                path=path,
                disposition=disposition,
                reason_code=reason,
                message=message,
                value=value if not isinstance(value, (dict, list)) else None,
            ))
            if isinstance(value, dict):
                for key in sorted(value):
                    visit(value[key], f"{path}.{key}")
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    visit(item, f"{path}[{index}]")

        for key in sorted(data):
            visit(data[key], key)
        return fields

    @staticmethod
    def _counts(graph_fields: list[FieldReport], objects: list[ObjectReport]) -> MappingCounts:
        all_fields = [*graph_fields, *(field for item in objects for field in item.fields)]
        return MappingCounts(
            supported_objects=sum(item.disposition == "supported" for item in objects),
            partial_objects=sum(item.disposition == "partial" for item in objects),
            unmapped_objects=sum(item.disposition == "unmapped" for item in objects),
            blocked_objects=sum(item.disposition == "blocked" for item in objects),
            supported_fields=sum(item.disposition == "supported" for item in all_fields),
            unmapped_fields=sum(item.disposition == "unmapped" for item in all_fields),
            blocked_fields=sum(item.disposition == "blocked" for item in all_fields),
        )

    @staticmethod
    def _preview(objects: list[ObjectReport]) -> DexpiMappingPreview:
        preview_objects = []
        for item in objects:
            if item.disposition not in {"supported", "partial"}:
                continue
            preview_objects.append(PreviewObject(
                object_type=item.object_type,
                canonical_id=item.canonical_id,
                kind=item.kind,
                supported_fields={
                    field.path: field.value
                    for field in item.fields
                    if field.disposition == "supported" and field.value is not None
                },
            ))
        return DexpiMappingPreview(objects=preview_objects)

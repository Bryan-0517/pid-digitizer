from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import TypeAliasType


Normalized = Annotated[float, Field(ge=0, le=1)]
Confidence = Annotated[float, Field(ge=0, le=1)]
JsonValue = TypeAliasType(
    "JsonValue",
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"],
)


class DomainModel(BaseModel):
    model_config = ConfigDict(alias_generator=lambda value: _to_camel(value), populate_by_name=True, extra="forbid")


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class Point(DomainModel):
    x: Normalized
    y: Normalized


class BoundingBox(DomainModel):
    x: Normalized
    y: Normalized
    width: Normalized
    height: Normalized

    @model_validator(mode="after")
    def validate_extent(self) -> BoundingBox:
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("bounding box must remain within normalized [0,1] bounds")
        return self


class EntityGeometry(DomainModel):
    bbox: BoundingBox | None = None
    polygon: list[Point] | None = None
    anchor_points: list[Point] | None = None


class ConnectionGeometry(DomainModel):
    polyline: list[Point] | None = None


class EvidenceRef(DomainModel):
    id: str
    source_type: Literal[
        "page_image", "ocr", "model", "spreadsheet", "external_document", "human"
    ]
    source_ref: str
    page_id: str | None = None
    region: BoundingBox | None = None
    raw_text: str | None = None
    note: str | None = None
    confidence: Confidence | None = None


class Assertion(DomainModel):
    mode: Literal["observed", "inferred", "human_added"]
    review_status: Literal[
        "unreviewed", "confirmed", "corrected", "rejected", "needs_source"
    ]


class DexpiMetadata(DomainModel):
    suggested_class: str | None = None
    mapping_status: Literal["not_checked", "mappable", "partial", "blocked"] | None = None


class EngineeringEntity(DomainModel):
    id: str
    document_id: str
    page_id: str
    kind: Literal["equipment", "valve", "instrument", "boundary", "text", "unknown"]
    subtype: str | None = None
    tag: str | None = None
    display_name: str | None = None
    properties: dict[str, JsonValue]
    geometry: EntityGeometry | None = None
    confidence: Confidence | None = None
    assertion: Assertion
    provenance: list[EvidenceRef]
    dexpi: DexpiMetadata | None = None
    created_at: str
    updated_at: str


class EngineeringConnection(DomainModel):
    id: str
    document_id: str
    source_entity_id: str
    target_entity_id: str
    allow_self_loop: bool = False
    kind: Literal["process", "utility", "signal", "ownership", "reference", "unknown"]
    medium: str | None = None
    direction: Literal[
        "source_to_target", "target_to_source", "undirected", "unknown"
    ] | None = None
    geometry: ConnectionGeometry | None = None
    properties: dict[str, JsonValue]
    confidence: Confidence | None = None
    assertion: Assertion
    provenance: list[EvidenceRef]
    created_at: str
    updated_at: str


class GraphMetadata(DomainModel):
    name: str | None = None
    description: str | None = None
    source_kind: Literal["pid", "pfd", "hmi", "dcs", "unknown"] | None = None


class EngineeringGraph(DomainModel):
    schema_version: Literal["0.1"]
    document_id: str
    entities: list[EngineeringEntity]
    connections: list[EngineeringConnection]
    metadata: GraphMetadata

    @model_validator(mode="after")
    def validate_graph_integrity(self) -> EngineeringGraph:
        entity_ids = [entity.id for entity in self.entities]
        duplicate_entities = _duplicates(entity_ids)
        if duplicate_entities:
            raise ValueError(f"duplicate entity IDs: {', '.join(duplicate_entities)}")

        connection_ids = [connection.id for connection in self.connections]
        duplicate_connections = _duplicates(connection_ids)
        if duplicate_connections:
            raise ValueError(f"duplicate connection IDs: {', '.join(duplicate_connections)}")

        known_entities = set(entity_ids)
        for connection in self.connections:
            if connection.source_entity_id not in known_entities:
                raise ValueError(
                    f"connection {connection.id} references missing source entity "
                    f"{connection.source_entity_id}"
                )
            if connection.target_entity_id not in known_entities:
                raise ValueError(
                    f"connection {connection.id} references missing target entity "
                    f"{connection.target_entity_id}"
                )
            if (
                connection.source_entity_id == connection.target_entity_id
                and not connection.allow_self_loop
            ):
                raise ValueError(
                    f"connection {connection.id} is a self-loop without allowSelfLoop=true"
                )
        return self


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


class Document(DomainModel):
    id: str
    name: str
    source_type: Literal["image", "pdf"]
    status: Literal["uploaded", "processing", "ready", "error"]
    created_at: str
    updated_at: str


class DocumentPage(DomainModel):
    id: str
    document_id: str
    page_number: int
    image_uri: str
    width_px: int
    height_px: int


class DigitizationJob(DomainModel):
    id: str
    document_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    provider: str
    provider_model: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    warnings: list[str]
    error: str | None = None


class GraphRevision(DomainModel):
    id: str
    document_id: str
    object_type: Literal["entity", "connection"]
    object_id: str
    operation: Literal["create", "update", "delete"]
    field_path: str | None = None
    before: JsonValue | None = None
    after: JsonValue | None = None
    actor_type: Literal["user", "model", "system"]
    actor_id: str | None = None
    created_at: str

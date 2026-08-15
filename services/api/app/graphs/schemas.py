from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import JsonValue


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class AssertionPatch(BaseModel):
    model_config = ConfigDict(alias_generator=lambda value: _to_camel(value), populate_by_name=True, extra="forbid")
    review_status: Literal["unreviewed", "confirmed", "corrected", "rejected", "needs_source"]


class EntityPatch(BaseModel):
    model_config = ConfigDict(alias_generator=lambda value: _to_camel(value), populate_by_name=True, extra="forbid")

    kind: Literal["equipment", "valve", "instrument", "boundary", "text", "unknown"] | None = None
    subtype: str | None = None
    tag: str | None = None
    display_name: str | None = None
    properties: dict[str, JsonValue] | None = None
    assertion: AssertionPatch | None = None


ConnectionKind = Literal["process", "utility", "signal", "ownership", "reference", "unknown"]
ConnectionDirection = Literal["source_to_target", "target_to_source", "undirected", "unknown"]


class ConnectionCreate(BaseModel):
    model_config = ConfigDict(alias_generator=lambda value: _to_camel(value), populate_by_name=True, extra="forbid")

    source_entity_id: str
    target_entity_id: str
    kind: ConnectionKind
    medium: str | None = None
    direction: ConnectionDirection | None = None
    properties: dict[str, JsonValue] = Field(default_factory=dict)
    assertion: AssertionPatch
    allow_self_loop: bool = False


class ConnectionPatch(BaseModel):
    model_config = ConfigDict(alias_generator=lambda value: _to_camel(value), populate_by_name=True, extra="forbid")

    source_entity_id: str | None = None
    target_entity_id: str | None = None
    kind: ConnectionKind | None = None
    medium: str | None = None
    direction: ConnectionDirection | None = None
    properties: dict[str, JsonValue] | None = None
    assertion: AssertionPatch | None = None
    allow_self_loop: bool | None = None

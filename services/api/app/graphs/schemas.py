from typing import Literal

from pydantic import BaseModel, ConfigDict

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

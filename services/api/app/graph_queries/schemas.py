from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.domain.models import Assertion, DomainModel, EngineeringEntity, EvidenceRef


ConnectionKind = Literal["process", "utility", "signal", "ownership", "reference", "unknown"]
Outcome = Literal["ok", "not_found", "ambiguous", "no_path"]


class KindFilter(DomainModel):
    connection_kinds: list[ConnectionKind] | None = None


class NeighborsQuery(KindFilter):
    operation: Literal["neighbors"]
    entity_id: str


class UpstreamQuery(KindFilter):
    operation: Literal["upstream"]
    entity_id: str


class DownstreamQuery(KindFilter):
    operation: Literal["downstream"]
    entity_id: str


class ShortestPathQuery(KindFilter):
    operation: Literal["shortest_path"]
    source_entity_id: str
    target_entity_id: str
    direction_mode: Literal["directed", "undirected"] = "directed"


class EntityLookupQuery(DomainModel):
    operation: Literal["entity_lookup"]
    entity_id: str | None = None
    tag: str | None = None

    @model_validator(mode="after")
    def exactly_one_lookup_key(self) -> EntityLookupQuery:
        if (self.entity_id is None) == (self.tag is None):
            raise ValueError("exactly one of entityId or tag is required")
        return self


GraphQueryRequest = Annotated[
    NeighborsQuery | UpstreamQuery | DownstreamQuery | ShortestPathQuery | EntityLookupQuery,
    Field(discriminator="operation"),
]


class ConnectionResult(DomainModel):
    id: str
    source_entity_id: str
    target_entity_id: str
    kind: ConnectionKind
    direction: Literal["source_to_target", "target_to_source", "undirected", "unknown"] | None
    assertion: Assertion
    provenance: list[EvidenceRef]
    confidence: float | None


class PathResult(DomainModel):
    entity_ids: list[str]
    connection_ids: list[str]


class AppliedFilters(DomainModel):
    connection_kinds: list[ConnectionKind]
    direction_mode: Literal["directed", "undirected"] | None = None


class GraphQueryResult(DomainModel):
    operation: Literal["neighbors", "upstream", "downstream", "shortest_path", "entity_lookup"]
    outcome: Outcome
    entity_ids: list[str] = Field(default_factory=list)
    connection_ids: list[str] = Field(default_factory=list)
    paths: list[PathResult] = Field(default_factory=list)
    entities: list[EngineeringEntity] = Field(default_factory=list)
    connections: list[ConnectionResult] = Field(default_factory=list)
    applied_filters: AppliedFilters | None = None

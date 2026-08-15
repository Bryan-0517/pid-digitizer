from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import EngineeringConnection, EngineeringEntity, EngineeringGraph, GraphMetadata
from app.graphs.db_models import GraphConnectionRecord, GraphEntityRecord, GraphRevisionRecord
from app.graphs.fixture import create_demo_graph
from app.graphs.schemas import ConnectionCreate, ConnectionPatch, EntityPatch


class GraphRepository:
    def __init__(self, session: Session):
        self.session = session

    def graph(self, document_id: str) -> EngineeringGraph:
        entity_records = self.session.scalars(
            select(GraphEntityRecord).where(GraphEntityRecord.document_id == document_id)
        ).all()
        connection_records = self.session.scalars(
            select(GraphConnectionRecord).where(GraphConnectionRecord.document_id == document_id)
        ).all()
        entities = [entity_from_record(record) for record in entity_records]
        connections = [connection_from_record(record) for record in connection_records]
        is_demo = any(
            evidence.source_ref == "t004-mock-fixture"
            for entity in entities
            for evidence in entity.provenance
        )
        return EngineeringGraph(
            schema_version="0.1",
            document_id=document_id,
            entities=entities,
            connections=connections,
            metadata=GraphMetadata(
                name="T004 mock overlay" if is_demo else None,
                description=(
                    "Synthetic demo fixture; not verified engineering truth." if is_demo else None
                ),
                source_kind="unknown" if is_demo else None,
            ),
        )

    def seed_demo_if_empty(self, document_id: str, page_id: str) -> None:
        existing = self.session.scalar(
            select(GraphEntityRecord.id).where(GraphEntityRecord.document_id == document_id).limit(1)
        )
        if existing is not None:
            return
        graph = create_demo_graph(document_id, page_id)
        self.session.add_all([entity_record(entity) for entity in graph.entities])
        self.session.flush()
        self.session.add_all([connection_record(connection) for connection in graph.connections])
        self.session.commit()

    def patch_entity(self, entity_id: str, patch: EntityPatch) -> EngineeringEntity | None:
        record = self.session.get(GraphEntityRecord, entity_id)
        if record is None:
            return None
        before_entity = entity_from_record(record)
        changes = patch.model_dump(exclude_unset=True)
        if changes.get("kind") is None and "kind" in changes:
            raise ValueError("kind cannot be null")
        if changes.get("properties") is None and "properties" in changes:
            raise ValueError("properties cannot be null")

        candidate_data = before_entity.model_dump(by_alias=True)
        for field in ("kind", "subtype", "tag", "display_name", "properties"):
            if field in changes:
                candidate_data[_to_camel(field)] = changes[field]
        if "assertion" in changes and changes["assertion"] is not None:
            candidate_data["assertion"]["reviewStatus"] = changes["assertion"]["review_status"]
        candidate_data["updatedAt"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        candidate = EngineeringEntity.model_validate(candidate_data)

        field_changes = _field_changes(before_entity, candidate, changes)
        if not field_changes:
            return before_entity
        record.kind = candidate.kind
        record.subtype = candidate.subtype
        record.tag = candidate.tag
        record.display_name = candidate.display_name
        record.properties = candidate.properties
        record.assertion = candidate.assertion.model_dump(by_alias=True)
        record.updated_at = _parse_timestamp(candidate.updated_at)
        now = datetime.now(UTC)
        self.session.add_all([
            GraphRevisionRecord(
                id=str(uuid4()), document_id=record.document_id, object_type="entity",
                object_id=record.id, operation="update", field_path=path,
                before=before, after=after, actor_type="user", created_at=now,
            )
            for path, before, after in field_changes
        ])
        self.session.commit()
        return candidate

    def create_connection(
        self, document_id: str, request: ConnectionCreate
    ) -> EngineeringConnection:
        now = datetime.now(UTC)
        timestamp = now.isoformat().replace("+00:00", "Z")
        connection = EngineeringConnection.model_validate({
            "id": str(uuid4()),
            "documentId": document_id,
            **request.model_dump(by_alias=True),
            "assertion": {
                "mode": "human_added",
                "reviewStatus": request.assertion.review_status,
            },
            "provenance": [],
            "createdAt": timestamp,
            "updatedAt": timestamp,
        })
        graph = self.graph(document_id)
        EngineeringGraph.model_validate({
            **graph.model_dump(by_alias=True),
            "connections": [
                *[item.model_dump(by_alias=True) for item in graph.connections],
                connection.model_dump(by_alias=True),
            ],
        })
        self.session.add(connection_record(connection))
        self.session.add(GraphRevisionRecord(
            id=str(uuid4()), document_id=document_id, object_type="connection",
            object_id=connection.id, operation="create", field_path="$",
            before=None, after=connection.model_dump(by_alias=True, exclude_none=True),
            actor_type="user", created_at=now,
        ))
        self.session.commit()
        return connection

    def patch_connection(
        self, connection_id: str, patch: ConnectionPatch
    ) -> EngineeringConnection | None:
        record = self.session.get(GraphConnectionRecord, connection_id)
        if record is None:
            return None
        before_connection = connection_from_record(record)
        changes = patch.model_dump(exclude_unset=True)
        for required in (
            "source_entity_id", "target_entity_id", "kind", "properties", "allow_self_loop"
        ):
            if required in changes and changes[required] is None:
                raise ValueError(f"{_to_camel(required)} cannot be null")

        candidate_data = before_connection.model_dump(by_alias=True)
        for field in (
            "source_entity_id", "target_entity_id", "kind", "medium", "direction",
            "properties", "allow_self_loop",
        ):
            if field in changes:
                candidate_data[_to_camel(field)] = changes[field]
        if "assertion" in changes and changes["assertion"] is not None:
            candidate_data["assertion"]["reviewStatus"] = changes["assertion"]["review_status"]
        candidate_data["updatedAt"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        candidate = EngineeringConnection.model_validate(candidate_data)

        graph = self.graph(record.document_id)
        EngineeringGraph.model_validate({
            **graph.model_dump(by_alias=True),
            "connections": [
                (candidate if item.id == connection_id else item).model_dump(by_alias=True)
                for item in graph.connections
            ],
        })
        field_changes = _connection_field_changes(before_connection, candidate, changes)
        if not field_changes:
            return before_connection
        record.source_entity_id = candidate.source_entity_id
        record.target_entity_id = candidate.target_entity_id
        record.kind = candidate.kind
        record.medium = candidate.medium
        record.direction = candidate.direction
        record.properties = candidate.properties
        record.assertion = candidate.assertion.model_dump(by_alias=True)
        record.allow_self_loop = candidate.allow_self_loop
        record.updated_at = _parse_timestamp(candidate.updated_at)
        now = datetime.now(UTC)
        self.session.add_all([
            GraphRevisionRecord(
                id=str(uuid4()), document_id=record.document_id, object_type="connection",
                object_id=record.id, operation="update", field_path=path,
                before=before, after=after, actor_type="user", created_at=now,
            )
            for path, before, after in field_changes
        ])
        self.session.commit()
        return candidate

    def delete_connection(self, connection_id: str) -> EngineeringConnection | None:
        record = self.session.get(GraphConnectionRecord, connection_id)
        if record is None:
            return None
        connection = connection_from_record(record)
        now = datetime.now(UTC)
        revision = GraphRevisionRecord(
            id=str(uuid4()), document_id=record.document_id, object_type="connection",
            object_id=record.id, operation="delete", field_path="$",
            before=connection.model_dump(by_alias=True, exclude_none=True), after=None,
            actor_type="user", created_at=now,
        )
        self.session.delete(record)
        self.session.add(revision)
        self.session.commit()
        return connection


def entity_record(entity: EngineeringEntity) -> GraphEntityRecord:
    return GraphEntityRecord(
        id=entity.id, document_id=entity.document_id, page_id=entity.page_id, kind=entity.kind,
        subtype=entity.subtype, tag=entity.tag, display_name=entity.display_name,
        properties=entity.properties,
        geometry=entity.geometry.model_dump(by_alias=True, exclude_none=True) if entity.geometry else None,
        confidence=entity.confidence, assertion=entity.assertion.model_dump(by_alias=True),
        provenance=[item.model_dump(by_alias=True, exclude_none=True) for item in entity.provenance],
        dexpi=entity.dexpi.model_dump(by_alias=True, exclude_none=True) if entity.dexpi else None,
        created_at=_parse_timestamp(entity.created_at), updated_at=_parse_timestamp(entity.updated_at),
    )


def connection_record(connection: EngineeringConnection) -> GraphConnectionRecord:
    return GraphConnectionRecord(
        id=connection.id, document_id=connection.document_id,
        source_entity_id=connection.source_entity_id, target_entity_id=connection.target_entity_id,
        allow_self_loop=connection.allow_self_loop, kind=connection.kind, medium=connection.medium,
        direction=connection.direction,
        geometry=connection.geometry.model_dump(by_alias=True, exclude_none=True) if connection.geometry else None,
        properties=connection.properties, confidence=connection.confidence,
        assertion=connection.assertion.model_dump(by_alias=True),
        provenance=[item.model_dump(by_alias=True, exclude_none=True) for item in connection.provenance],
        created_at=_parse_timestamp(connection.created_at), updated_at=_parse_timestamp(connection.updated_at),
    )


def entity_from_record(record: GraphEntityRecord) -> EngineeringEntity:
    return EngineeringEntity.model_validate({
        "id": record.id, "documentId": record.document_id, "pageId": record.page_id,
        "kind": record.kind, "subtype": record.subtype, "tag": record.tag,
        "displayName": record.display_name, "properties": record.properties,
        "geometry": record.geometry, "confidence": record.confidence,
        "assertion": record.assertion, "provenance": record.provenance, "dexpi": record.dexpi,
        "createdAt": _format_timestamp(record.created_at), "updatedAt": _format_timestamp(record.updated_at),
    })


def connection_from_record(record: GraphConnectionRecord) -> EngineeringConnection:
    return EngineeringConnection.model_validate({
        "id": record.id, "documentId": record.document_id,
        "sourceEntityId": record.source_entity_id, "targetEntityId": record.target_entity_id,
        "allowSelfLoop": record.allow_self_loop, "kind": record.kind, "medium": record.medium,
        "direction": record.direction, "geometry": record.geometry, "properties": record.properties,
        "confidence": record.confidence, "assertion": record.assertion,
        "provenance": record.provenance, "createdAt": _format_timestamp(record.created_at),
        "updatedAt": _format_timestamp(record.updated_at),
    })


def _field_changes(before: EngineeringEntity, after: EngineeringEntity, changes: dict) -> list[tuple[str, object, object]]:
    result: list[tuple[str, object, object]] = []
    for field in ("kind", "subtype", "tag", "display_name", "properties"):
        if field in changes and getattr(before, field) != getattr(after, field):
            result.append((_to_camel(field), getattr(before, field), getattr(after, field)))
    if "assertion" in changes and before.assertion.review_status != after.assertion.review_status:
        result.append(("assertion.reviewStatus", before.assertion.review_status, after.assertion.review_status))
    return result


def _connection_field_changes(
    before: EngineeringConnection, after: EngineeringConnection, changes: dict
) -> list[tuple[str, object, object]]:
    result: list[tuple[str, object, object]] = []
    for field in (
        "source_entity_id", "target_entity_id", "kind", "medium", "direction",
        "properties", "allow_self_loop",
    ):
        if field in changes and getattr(before, field) != getattr(after, field):
            result.append((_to_camel(field), getattr(before, field), getattr(after, field)))
    if "assertion" in changes and before.assertion.review_status != after.assertion.review_status:
        result.append(("assertion.reviewStatus", before.assertion.review_status, after.assertion.review_status))
    return result


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")

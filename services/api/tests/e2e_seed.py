"""T018-only canonical graph setup for the disposable E2E database.

Upload does not accept digitization proposals or create canonical graph objects. This helper is
mounted only into the isolated E2E API container and writes a minimal mechanics fixture after the
real IMG_6807.JPG upload. Its labels, topology, and geometry are explicit test data, not benchmark
semantic truth and not verified plant engineering information.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.database import SessionLocal
from app.documents.db_models import DocumentPageRecord, DocumentRecord
from app.domain.models import EngineeringConnection, EngineeringEntity, EngineeringGraph, GraphMetadata
from app.graphs.db_models import GraphEntityRecord, GraphRevisionRecord
from app.graphs.repository import connection_record, entity_record


ENTITY_A_ID = "t018:e2e-source"
ENTITY_B_ID = "t018:e2e-neighbor"
CONNECTION_ID = "t018:e2e-process-connection"


def seed(document_id: str, page_id: str) -> None:
    with SessionLocal() as session:
        document = session.get(DocumentRecord, document_id)
        page = session.get(DocumentPageRecord, page_id)
        if document is None or page is None or page.document_id != document_id:
            raise SystemExit("documentId/pageId do not identify the uploaded E2E document page")
        if document.name != "IMG_6807.JPG" or document.status != "ready":
            raise SystemExit("seed is restricted to the ready IMG_6807.JPG E2E upload")

        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        provenance_note = (
            "T018 mechanics fixture only; not benchmark truth or verified engineering data."
        )
        entities = [
            EngineeringEntity.model_validate({
                "id": ENTITY_A_ID, "documentId": document_id, "pageId": page_id,
                "kind": "equipment", "tag": "T018-A", "displayName": "E2E source fixture",
                "properties": {}, "geometry": {"bbox": {"x": .16, "y": .28, "width": .12, "height": .12}},
                "confidence": .5, "assertion": {"mode": "human_added", "reviewStatus": "unreviewed"},
                "provenance": [{"id": "t018-evidence-a", "sourceType": "human",
                    "sourceRef": "t018-e2e-fixture", "pageId": page_id, "note": provenance_note}],
                "createdAt": timestamp, "updatedAt": timestamp,
            }),
            EngineeringEntity.model_validate({
                "id": ENTITY_B_ID, "documentId": document_id, "pageId": page_id,
                "kind": "equipment", "tag": "T018-B", "displayName": "E2E neighbor fixture",
                "properties": {}, "geometry": {"bbox": {"x": .55, "y": .28, "width": .12, "height": .12}},
                "confidence": .5, "assertion": {"mode": "human_added", "reviewStatus": "unreviewed"},
                "provenance": [{"id": "t018-evidence-b", "sourceType": "human",
                    "sourceRef": "t018-e2e-fixture", "pageId": page_id, "note": provenance_note}],
                "createdAt": timestamp, "updatedAt": timestamp,
            }),
        ]
        connection = EngineeringConnection.model_validate({
            "id": CONNECTION_ID, "documentId": document_id,
            "sourceEntityId": ENTITY_A_ID, "targetEntityId": ENTITY_B_ID,
            "kind": "process", "direction": "source_to_target",
            "geometry": {"polyline": [{"x": .28, "y": .34}, {"x": .55, "y": .34}]},
            "properties": {}, "confidence": .5,
            "assertion": {"mode": "human_added", "reviewStatus": "unreviewed"},
            "provenance": [{"id": "t018-evidence-connection", "sourceType": "human",
                "sourceRef": "t018-e2e-fixture", "pageId": page_id, "note": provenance_note}],
            "createdAt": timestamp, "updatedAt": timestamp,
        })
        EngineeringGraph(schema_version="0.1", document_id=document_id,
                         entities=entities, connections=[connection],
                         metadata=GraphMetadata(name="T018 mechanics fixture", source_kind="dcs"))
        session.add_all([entity_record(item) for item in entities])
        session.flush()
        session.add(connection_record(connection))
        session.commit()
        print(json.dumps({"documentId": document_id, "pageId": page_id,
                          "entityIds": [ENTITY_A_ID, ENTITY_B_ID],
                          "connectionIds": [CONNECTION_ID]}))


def assert_edit(document_id: str, expected_display_name: str) -> None:
    with SessionLocal() as session:
        entity = session.get(GraphEntityRecord, ENTITY_A_ID)
        revisions = session.scalar(select(func.count()).select_from(GraphRevisionRecord).where(
            GraphRevisionRecord.document_id == document_id,
            GraphRevisionRecord.object_id == ENTITY_A_ID,
            GraphRevisionRecord.operation == "update",
            GraphRevisionRecord.field_path == "displayName",
        ))
        if entity is None or entity.document_id != document_id or entity.display_name != expected_display_name:
            raise SystemExit("persisted E2E entity edit does not match")
        if revisions != 1:
            raise SystemExit(f"expected one displayName revision, found {revisions}")
        print(json.dumps({"entityId": ENTITY_A_ID, "displayName": entity.display_name,
                          "displayNameRevisionCount": revisions}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    seed_parser = subparsers.add_parser("seed")
    seed_parser.add_argument("document_id")
    seed_parser.add_argument("page_id")
    assert_parser = subparsers.add_parser("assert-edit")
    assert_parser.add_argument("document_id")
    assert_parser.add_argument("expected_display_name")
    arguments = parser.parse_args()
    if arguments.command == "seed":
        seed(arguments.document_id, arguments.page_id)
    else:
        assert_edit(arguments.document_id, arguments.expected_display_name)

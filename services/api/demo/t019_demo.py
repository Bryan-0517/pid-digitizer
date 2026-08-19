"""Prepare and validate the isolated, non-production T019 local demo.

This module is never imported by production routing. It validates one fixed saved entity proposal,
creates two inferred/unreviewed canonical entities, and adds one separately human-reviewed,
directionless source-image reference association. It is not a proposal-acceptance or graph-import
product boundary.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, func, select

from app.chat.schemas import ChatRequest
from app.chat.service import ChatService
from app.config import settings
from app.database import SessionLocal
from app.documents.db_models import DocumentPageRecord, DocumentRecord
from app.documents.service import normalize_upload, save_page, save_source
from app.domain.models import EngineeringConnection, EngineeringEntity, EngineeringGraph, GraphMetadata
from app.graph_queries.schemas import NeighborsQuery
from app.graph_queries.service import GraphQueryService
from app.graphs.db_models import GraphConnectionRecord, GraphEntityRecord, GraphRevisionRecord
from app.graphs.repository import GraphRepository, connection_record, entity_record


DEFAULT_MANIFEST = Path("/demo/t019-manifest.json")
DEFAULT_PROPOSAL = Path("/demo/proposal.json")
DEFAULT_IMAGE = Path("/demo/IMG_6807.JPG")
FIXED_TIMESTAMP = "2026-08-16T00:00:00Z"
EXPECTED_ENTITIES = {
    "instruments:r1c0:inst-3": ("t019:entity:fi-0828", "FI_0828", "instrument", None),
    "valves:r1c0:valve-7": ("t019:entity:fv-0827", "FV_0827", "valve", "FV"),
}
EXPECTED_CONNECTION_ID = "t019:connection:fi-0828--fv-0827"


def load_and_validate_assets(
    manifest_path: Path = DEFAULT_MANIFEST,
    proposal_path: Path = DEFAULT_PROPOSAL,
    image_path: Path = DEFAULT_IMAGE,
) -> tuple[dict, dict]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    _expect_hash(image_path, manifest["sourceImage"]["sha256"])
    _expect_hash(proposal_path, manifest["savedProposal"]["sha256"])
    saved = manifest["savedProposal"]
    if proposal.get("snapshotLabel") != saved["snapshotLabel"]:
        raise ValueError("saved proposal snapshot label mismatch")
    if proposal.get("experimentId") != saved["experimentId"]:
        raise ValueError("saved proposal experiment mismatch")
    if proposal.get("sourceFilename") != manifest["sourceImage"]["filename"]:
        raise ValueError("saved proposal source-image identity mismatch")
    candidates = proposal.get("mergedProposal", {}).get("candidates", [])
    if len(candidates) != saved["entityCandidateCount"]:
        raise ValueError("saved proposal entity-candidate count mismatch")
    if proposal.get("topologyProposalCount") != 0 or saved["topologyProposalCount"] != 0:
        raise ValueError("authoritative T019 proposal must contain zero topology proposals")
    if proposal.get("canonicalGraphMutated") is not False:
        raise ValueError("saved proposal must record canonicalGraphMutated=false")
    by_id = {candidate["candidateId"]: candidate for candidate in candidates}
    manifest_entities = {
        item["proposalCandidateId"]: (item["canonicalId"], item["tag"], item["kind"], item["subtype"])
        for item in manifest["entities"]
    }
    if manifest_entities != EXPECTED_ENTITIES:
        raise ValueError("prepared entities differ from the audited FI_0828/FV_0827 pair")
    for entity in manifest["entities"]:
        candidate = by_id.get(entity["proposalCandidateId"])
        if candidate is None:
            raise ValueError(f"missing selected candidate {entity['proposalCandidateId']}")
        for field in ("kind", "subtype", "tag", "displayName", "geometry", "confidence"):
            if _without_empty_geometry(candidate.get(field)) != _without_empty_geometry(entity.get(field)):
                raise ValueError(f"manifest field {field} differs from {entity['proposalCandidateId']}")
        expected_provenance = entity["proposalProvenance"]
        if len(candidate.get("provenance", [])) != 1 or candidate["provenance"][0] != expected_provenance:
            raise ValueError(f"manifest provenance differs from {entity['proposalCandidateId']}")
        if entity["assertion"] != {"mode": "inferred", "reviewStatus": "unreviewed"}:
            raise ValueError("proposal-derived entities must start inferred/unreviewed")
        if "manually verified against IMG_6807" not in entity.get("geometryReview", ""):
            raise ValueError("prepared entity geometry review is missing")
    connections = manifest["connections"]
    if len(connections) != 1:
        raise ValueError("T019 manifest must contain exactly one connection")
    connection = connections[0]
    if (connection["canonicalId"] != EXPECTED_CONNECTION_ID
            or connection["sourceEntityId"] != "t019:entity:fi-0828"
            or connection["targetEntityId"] != "t019:entity:fv-0827"
            or connection["kind"] != "reference"):
        raise ValueError("prepared connection differs from the audited FI_0828/FV_0827 reference")
    if connection["modelTopologyCandidateId"] is not None:
        raise ValueError("human-reviewed connection cannot claim a model topology candidate")
    if connection["direction"] != "unknown" or connection["geometry"] is not None:
        raise ValueError("human-reviewed connection must not assert direction or geometry")
    if connection["assertion"] != {"mode": "human_added", "reviewStatus": "confirmed"}:
        raise ValueError("human-reviewed connection metadata mismatch")
    note = connection["humanProvenance"]["note"]
    for required in ("direction not established", "not model output", "not derived from benchmark truth"):
        if required not in note:
            raise ValueError(f"human provenance note is missing: {required}")
    return manifest, proposal


def build_graph(manifest: dict, document_id: str, page_id: str) -> EngineeringGraph:
    entities = []
    for item in manifest["entities"]:
        candidate_id = item["proposalCandidateId"]
        provenance = item["proposalProvenance"]
        entities.append(EngineeringEntity.model_validate({
            "id": item["canonicalId"], "documentId": document_id, "pageId": page_id,
            "kind": item["kind"], "subtype": item["subtype"], "tag": item["tag"],
            "displayName": item["displayName"], "properties": {}, "geometry": item["geometry"],
            "confidence": item["confidence"], "assertion": item["assertion"],
            "provenance": [{"id": f"t019:model:{candidate_id}", "sourceType": "model",
                "sourceRef": provenance["sourceRef"], "pageId": page_id,
                "rawText": provenance["evidenceText"],
                "note": f"candidateId={candidate_id}; {provenance['note']}"}],
            "createdAt": FIXED_TIMESTAMP, "updatedAt": FIXED_TIMESTAMP,
        }))
    item = manifest["connections"][0]
    connection = EngineeringConnection.model_validate({
        "id": item["canonicalId"], "documentId": document_id,
        "sourceEntityId": item["sourceEntityId"], "targetEntityId": item["targetEntityId"],
        "kind": item["kind"], "direction": item["direction"], "properties": {},
        "confidence": item["confidence"], "assertion": item["assertion"],
        "provenance": [{"id": "t019:human:reviewed-connectivity", "sourceType": "human",
            "sourceRef": item["humanProvenance"]["sourceRef"], "pageId": page_id,
            "note": f"{item['humanReviewStatement']} {item['humanProvenance']['note']}"}],
        "createdAt": FIXED_TIMESTAMP, "updatedAt": FIXED_TIMESTAMP,
    })
    return EngineeringGraph(schema_version="0.1", document_id=document_id, entities=entities,
                            connections=[connection], metadata=GraphMetadata(
                                name="T019 IMG_6807 prepared local demo", source_kind="dcs",
                                description="Proposal-derived entities plus one human-reviewed connection; not verified plant truth."))


def setup() -> dict:
    _require_isolated_demo_environment()
    manifest, _ = load_and_validate_assets()
    prepared = manifest["preparedDocument"]
    document_id, page_id = prepared["documentId"], prepared["pageId"]
    graph = build_graph(manifest, document_id, page_id)
    content = DEFAULT_IMAGE.read_bytes()
    normalized = normalize_upload(content, "image")
    timestamp = datetime.fromisoformat(FIXED_TIMESTAMP.replace("Z", "+00:00"))
    with SessionLocal() as session:
        _delete_prepared_records(session, document_id)
        document = DocumentRecord(id=document_id, name=prepared["name"], source_type="image",
                                  status="ready", created_at=timestamp, updated_at=timestamp)
        session.add(document)
        session.flush()
        save_source(content, normalized, settings.storage_dir, document_id)
        image_uri = save_page(normalized, settings.storage_dir, document_id, page_id)
        session.add(DocumentPageRecord(id=page_id, document_id=document_id, page_number=1,
                                       image_uri=image_uri, width_px=normalized.image.width,
                                       height_px=normalized.image.height))
        session.flush()
        session.add_all([entity_record(entity) for entity in graph.entities])
        session.flush()
        session.add(connection_record(graph.connections[0]))
        session.commit()
    return check()


def check() -> dict:
    _require_isolated_demo_environment()
    manifest, _ = load_and_validate_assets()
    prepared = manifest["preparedDocument"]
    with SessionLocal() as session:
        document = session.get(DocumentRecord, prepared["documentId"])
        page = session.get(DocumentPageRecord, prepared["pageId"])
        if document is None or page is None or page.document_id != prepared["documentId"]:
            raise ValueError("prepared Document/DocumentPage is missing or inconsistent")
        graph = GraphRepository(session).graph(prepared["documentId"])
        expected = build_graph(manifest, prepared["documentId"], prepared["pageId"])
        _assert_initial_graph(graph, expected)
        query = GraphQueryService().query(graph, NeighborsQuery(
            operation="neighbors", entity_id="t019:entity:fi-0828"))
        expected_chat = manifest["graphChat"]
        if query.entity_ids != ["t019:entity:fv-0827"] or query.connection_ids != expected_chat["expectedSupportingConnectionIds"]:
            raise ValueError("deterministic neighbor query differs from demo manifest")
        chat = asyncio.run(ChatService().respond(graph, ChatRequest(
            message=expected_chat["question"], verbalize=False)))
        if (chat.answer != expected_chat["expectedAnswer"]
                or chat.supporting_entity_ids != expected_chat["expectedSupportingEntityIds"]
                or chat.supporting_connection_ids != expected_chat["expectedSupportingConnectionIds"]
                or chat.verbalization_metadata is not None):
            raise ValueError("deterministic Graph Chat response differs from demo manifest")
        revisions = session.scalar(select(func.count()).select_from(GraphRevisionRecord).where(
            GraphRevisionRecord.document_id == prepared["documentId"]))
        if revisions != 0:
            raise ValueError("reset demo must begin without revision history")
    return {"status": "ready", "documentId": prepared["documentId"], "pageId": prepared["pageId"],
            "entityIds": expected_chat["expectedSupportingEntityIds"],
            "connectionIds": expected_chat["expectedSupportingConnectionIds"],
            "question": expected_chat["question"], "answer": expected_chat["expectedAnswer"],
            "topologyProposalCount": 0, "aiProviderInvoked": False}


def _assert_initial_graph(actual: EngineeringGraph, expected: EngineeringGraph) -> None:
    actual_entities = {item.id: item for item in actual.entities}
    for expected_entity in expected.entities:
        actual_entity = actual_entities.get(expected_entity.id)
        if actual_entity is None:
            raise ValueError(f"missing canonical entity {expected_entity.id}")
        for field in ("document_id", "page_id", "kind", "subtype", "tag", "display_name",
                      "properties", "geometry", "confidence", "assertion", "provenance"):
            if getattr(actual_entity, field) != getattr(expected_entity, field):
                raise ValueError(f"canonical entity field mismatch: {expected_entity.id}.{field}")
    if len(actual.entities) != 2 or len(actual.connections) != 1:
        raise ValueError("demo graph must contain exactly two entities and one connection")
    expected_connection = expected.connections[0]
    if actual.connections[0].model_dump(exclude={"created_at", "updated_at"}) != expected_connection.model_dump(exclude={"created_at", "updated_at"}):
        raise ValueError("human-reviewed canonical connection differs from manifest")


def _delete_prepared_records(session, document_id: str) -> None:
    session.execute(delete(GraphRevisionRecord).where(GraphRevisionRecord.document_id == document_id))
    session.execute(delete(GraphConnectionRecord).where(GraphConnectionRecord.document_id == document_id))
    session.execute(delete(GraphEntityRecord).where(GraphEntityRecord.document_id == document_id))
    session.execute(delete(DocumentPageRecord).where(DocumentPageRecord.document_id == document_id))
    session.execute(delete(DocumentRecord).where(DocumentRecord.id == document_id))
    session.commit()
    target = (settings.storage_dir / document_id).resolve()
    storage = settings.storage_dir.resolve()
    if target.parent != storage:
        raise RuntimeError("refusing to clean a path outside isolated demo storage")
    if target.exists():
        shutil.rmtree(target)


def _require_isolated_demo_environment() -> None:
    if not settings.database_url.rsplit("/", 1)[-1] == "pid_digitizer_demo":
        raise RuntimeError("T019 helper refuses to act outside pid_digitizer_demo")
    if settings.demo_mock_graph or settings.ai_provider or settings.ai_model or settings.ai_api_key:
        raise RuntimeError("T019 demo requires mock graph and all AI configuration disabled")
    if settings.pydexpi_export_enabled:
        raise RuntimeError("T019 demo requires pyDEXPI export disabled")


def _expect_hash(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"asset hash mismatch: {path}")


def _without_empty_geometry(value):
    if not isinstance(value, dict):
        return value
    return {key: item for key, item in value.items() if item is not None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["setup", "check"])
    arguments = parser.parse_args()
    result = setup() if arguments.command == "setup" else check()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))

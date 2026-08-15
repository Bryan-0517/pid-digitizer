from datetime import UTC, datetime

from app.domain.models import EngineeringConnection, EngineeringEntity, EngineeringGraph, GraphMetadata


def create_demo_graph(document_id: str, page_id: str) -> EngineeringGraph:
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    ids = {
        "equipment": f"{document_id}:mock-equipment-1",
        "valve": f"{document_id}:mock-valve-1",
        "instrument": f"{document_id}:mock-instrument-1",
        "boundary": f"{document_id}:mock-boundary-1",
    }

    def entity(entity_id: str, kind: str, bbox: dict, **labels: str) -> EngineeringEntity:
        return EngineeringEntity.model_validate(
            {
                "id": entity_id,
                "documentId": document_id,
                "pageId": page_id,
                "kind": kind,
                **labels,
                "properties": {},
                "geometry": {"bbox": bbox},
                "assertion": {"mode": "human_added", "reviewStatus": "unreviewed"},
                "provenance": [{
                    "id": f"evidence-{entity_id}",
                    "sourceType": "human",
                    "sourceRef": "t004-mock-fixture",
                    "pageId": page_id,
                    "note": "Explicit demo geometry only; not verified engineering truth.",
                }],
                "createdAt": timestamp,
                "updatedAt": timestamp,
            }
        )

    entities = [
        entity(ids["equipment"], "equipment", {"x": 0.12, "y": 0.24, "width": 0.18, "height": 0.22}, tag="P-MOCK-1"),
        entity(ids["valve"], "valve", {"x": 0.43, "y": 0.42, "width": 0.07, "height": 0.10}, tag="V-MOCK-1"),
        entity(ids["instrument"], "instrument", {"x": 0.62, "y": 0.18, "width": 0.09, "height": 0.12}, displayName="Mock indicator"),
        entity(ids["boundary"], "boundary", {"x": 0.82, "y": 0.39, "width": 0.10, "height": 0.16}),
    ]
    connections = [
        EngineeringConnection.model_validate({
            "id": f"{document_id}:mock-connection-with-geometry", "documentId": document_id,
            "sourceEntityId": ids["equipment"], "targetEntityId": ids["valve"],
            "kind": "process", "direction": "source_to_target",
            "geometry": {"polyline": [{"x": 0.30, "y": 0.35}, {"x": 0.38, "y": 0.35}, {"x": 0.46, "y": 0.42}]},
            "properties": {}, "assertion": {"mode": "human_added", "reviewStatus": "unreviewed"},
            "provenance": [{"id": "evidence-mock-connection-1", "sourceType": "human", "sourceRef": "t004-mock-fixture", "pageId": page_id}],
            "createdAt": timestamp, "updatedAt": timestamp,
        }),
        EngineeringConnection.model_validate({
            "id": f"{document_id}:mock-connection-without-geometry", "documentId": document_id,
            "sourceEntityId": ids["valve"], "targetEntityId": ids["boundary"],
            "kind": "process", "properties": {},
            "assertion": {"mode": "human_added", "reviewStatus": "unreviewed"},
            "provenance": [{"id": "evidence-mock-connection-2", "sourceType": "human", "sourceRef": "t004-mock-fixture", "pageId": page_id}],
            "createdAt": timestamp, "updatedAt": timestamp,
        }),
    ]
    return EngineeringGraph(
        schema_version="0.1",
        document_id=document_id,
        entities=entities,
        connections=connections,
        metadata=GraphMetadata(
            name="T004 mock overlay",
            description="Synthetic demo fixture; not verified engineering truth.",
            source_kind="unknown",
        ),
    )

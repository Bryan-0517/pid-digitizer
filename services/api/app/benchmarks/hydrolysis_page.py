from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image

from app.domain.models import EngineeringGraph

DOCUMENT_ID = "benchmark:hydrolysis"
SOURCE_FILENAME = "IMG_6807.JPG"
PAGE_ID = f"benchmark:hydrolysis:{SOURCE_FILENAME}"
GEOMETRY_STATUS = "missing_verified_geometry"


def build_page_fixture(graph_path: Path, image_path: Path) -> dict[str, Any]:
    if image_path.name != SOURCE_FILENAME:
        raise ValueError(f"expected source image {SOURCE_FILENAME}, got {image_path.name}")
    graph = EngineeringGraph.model_validate_json(graph_path.read_text(encoding="utf-8"))
    if graph.document_id != DOCUMENT_ID:
        raise ValueError(f"expected benchmark document {DOCUMENT_ID}")
    with Image.open(image_path) as image:
        image.verify()
    with Image.open(image_path) as image:
        width, height = image.size

    entities = [item for item in graph.entities if _references(item.provenance, SOURCE_FILENAME)]
    connections = [item for item in graph.connections if _references(item.provenance, SOURCE_FILENAME)]
    instruments = [item for item in entities if item.kind == "instrument"]
    objects = [*entities, *connections]
    multi_source = [item.id for item in objects if len({e.source_ref for e in item.provenance}) > 1]
    multi_screen = [
        item.id for item in objects
        if any(e.source_ref.upper().startswith("IMG_") and e.source_ref != SOURCE_FILENAME for e in item.provenance)
    ]
    object_index = [
        {
            "id": item.id,
            "objectType": "entity" if item in entities else "connection",
            "kind": item.kind,
            "geometryStatus": GEOMETRY_STATUS,
            "sourceRefs": sorted({e.source_ref for e in item.provenance}),
        }
        for item in objects
    ]
    return {
        "schemaVersion": "0.1",
        "documentId": DOCUMENT_ID,
        "pageId": PAGE_ID,
        "sourceFilename": SOURCE_FILENAME,
        "sourceImagePath": "benchmarks/hydrolysis/images/IMG_6807.JPG",
        "widthPx": width,
        "heightPx": height,
        "linkedEntityIds": [item.id for item in entities],
        "linkedConnectionIds": [item.id for item in connections],
        "linkedInstrumentIds": [item.id for item in instruments],
        "counts": {
            "entities": len(entities), "connections": len(connections),
            "instruments": len(instruments), "multiSourceObjects": len(multi_source),
            "multiScreenObjects": len(multi_screen),
        },
        "geometryCoverage": {
            "status": GEOMETRY_STATUS, "entitiesWithVerifiedGeometry": 0,
            "connectionsWithVerifiedGeometry": 0, "totalObjectsWithVerifiedGeometry": 0,
        },
        "multiSourceObjectIds": multi_source,
        "multiScreenObjectIds": multi_screen,
        "objects": object_index,
        "provenanceNotes": [
            "Page linkage is based only on explicit provenance sourceRef=IMG_6807.JPG.",
            "Page relevance does not mean exclusive ownership by this source screen.",
        ],
        "warnings": [
            "Hydrolysis reference data is pre-DEXPI and is not certified engineering truth.",
            "Verified geometry coverage is zero; no Canvas overlays may be rendered.",
        ],
    }


def write_page_fixture(fixture: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _references(provenance: list[Any], source: str) -> bool:
    return any(item.source_ref == source for item in provenance)

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image

from app.domain.models import EngineeringGraph

DOCUMENT_ID = "benchmark:hydrolysis"
SOURCE_FILENAME = "IMG_6807.JPG"
GEOMETRY_STATUS = "missing_verified_geometry"
DEV_SCREENS = (SOURCE_FILENAME,)


def build_page_fixture(graph_path: Path, image_path: Path) -> dict[str, Any]:
    source_filename = image_path.name
    page_id = f"{DOCUMENT_ID}:{source_filename}"
    graph = EngineeringGraph.model_validate_json(graph_path.read_text(encoding="utf-8"))
    if graph.document_id != DOCUMENT_ID:
        raise ValueError(f"expected benchmark document {DOCUMENT_ID}")
    with Image.open(image_path) as image:
        image.verify()
    with Image.open(image_path) as image:
        width, height = image.size

    entities = [item for item in graph.entities if _references(item.provenance, source_filename)]
    connections = [item for item in graph.connections if _references(item.provenance, source_filename)]
    instruments = [item for item in entities if item.kind == "instrument"]
    equipment = [item for item in entities if item.kind == "equipment"]
    boundaries = [item for item in entities if item.kind == "boundary"]
    objects = [*entities, *connections]
    multi_source = [item.id for item in objects if len({e.source_ref for e in item.provenance}) > 1]
    multi_screen = [
        item.id for item in objects
        if any(
            e.source_type == "page_image"
            and e.source_ref.upper().startswith("IMG_")
            and e.source_ref != source_filename
            for e in item.provenance
        )
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
    warnings = [
        "Hydrolysis reference data is pre-DEXPI and is not certified engineering truth.",
        "Verified geometry coverage is zero; no Canvas overlays may be rendered.",
    ]
    if multi_screen:
        warnings.append(
            f"{len(multi_screen)} linked object(s) explicitly cite multiple page images; "
            "page membership is non-exclusive."
        )
    return {
        "schemaVersion": "0.1",
        "documentId": DOCUMENT_ID,
        "pageId": page_id,
        "sourceFilename": source_filename,
        "sourceImagePath": f"benchmarks/hydrolysis/images/{source_filename}",
        "benchmarkSplit": "dev" if source_filename in DEV_SCREENS else "holdout",
        "widthPx": width,
        "heightPx": height,
        "linkedEntityIds": [item.id for item in entities],
        "linkedConnectionIds": [item.id for item in connections],
        "linkedInstrumentIds": [item.id for item in instruments],
        "counts": {
            "entities": len(entities), "equipment": len(equipment),
            "instruments": len(instruments), "boundaries": len(boundaries),
            "connections": len(connections),
            "multiSourceObjects": len(multi_source),
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
            f"Page linkage is based only on explicit page_image provenance sourceRef={source_filename}.",
            "Page relevance does not mean exclusive ownership by this source screen.",
            "Holdout semantic answers must not be included in extraction prompts.",
        ],
        "warnings": warnings,
    }


def write_page_fixture(fixture: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _references(provenance: list[Any], source: str) -> bool:
    return any(item.source_type == "page_image" and item.source_ref == source for item in provenance)


def build_benchmark_inventory(
    graph_path: Path, image_paths: list[Path]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fixtures = [build_page_fixture(graph_path, path) for path in sorted(image_paths)]
    usable = [fixture for fixture in fixtures if fixture["counts"]["entities"] > 0]
    inventory = {
        "schemaVersion": "0.1",
        "benchmark": "hydrolysis",
        "scopeRule": "explicit page_image provenance sourceRef equality only",
        "splits": {
            "dev": [name for name in DEV_SCREENS if any(f["sourceFilename"] == name for f in usable)],
            "holdout": [
                fixture["sourceFilename"]
                for fixture in usable
                if fixture["sourceFilename"] not in DEV_SCREENS
            ],
        },
        "screens": [
            {
                "sourceFilename": fixture["sourceFilename"],
                "benchmarkSplit": fixture["benchmarkSplit"],
                "widthPx": fixture["widthPx"],
                "heightPx": fixture["heightPx"],
                "linkedEntityCount": fixture["counts"]["entities"],
                "linkedEquipmentCount": fixture["counts"]["equipment"],
                "linkedInstrumentCount": fixture["counts"]["instruments"],
                "linkedBoundaryCount": fixture["counts"]["boundaries"],
                "linkedConnectionCount": fixture["counts"]["connections"],
                "verifiedEntityGeometryCount": fixture["geometryCoverage"]["entitiesWithVerifiedGeometry"],
                "verifiedConnectionGeometryCount": fixture["geometryCoverage"]["connectionsWithVerifiedGeometry"],
                "provenanceAmbiguityWarnings": fixture["warnings"],
                "multiScreenObjectCount": fixture["counts"]["multiScreenObjects"],
            }
            for fixture in usable
        ],
        "warnings": [
            "Hydrolysis references are pre-DEXPI and are not certified engineering truth.",
            "All page fixtures express semantic provenance relevance only; verified geometry is absent.",
            "Objects may cite multiple screens and therefore appear in multiple page fixtures.",
        ],
    }
    return usable, inventory

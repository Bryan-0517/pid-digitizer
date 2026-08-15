import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.domain.models import EngineeringGraph
from app.domain.validation import duplicate_tag_warnings


def entity(entity_id: str, *, tag: str | None = None) -> dict[str, object]:
    return {
        "id": entity_id,
        "documentId": "doc-1",
        "pageId": "page-1",
        "kind": "equipment",
        "tag": tag,
        "properties": {},
        "assertion": {"mode": "observed", "reviewStatus": "unreviewed"},
        "provenance": [
            {
                "id": f"evidence-{entity_id}",
                "sourceType": "page_image",
                "sourceRef": "page-1",
                "region": {"x": 0.1, "y": 0.2, "width": 0.2, "height": 0.2},
                "confidence": 0.8,
            }
        ],
        "createdAt": "2026-08-14T00:00:00Z",
        "updatedAt": "2026-08-14T00:00:00Z",
    }


def connection(
    connection_id: str = "c-1",
    source: str = "e-1",
    target: str = "e-2",
    *,
    allow_self_loop: bool | None = None,
) -> dict[str, object]:
    value: dict[str, object] = {
        "id": connection_id,
        "documentId": "doc-1",
        "sourceEntityId": source,
        "targetEntityId": target,
        "kind": "process",
        "geometry": {"polyline": [{"x": 0.2, "y": 0.3}, {"x": 0.8, "y": 0.7}]},
        "properties": {},
        "confidence": 0.7,
        "assertion": {"mode": "inferred", "reviewStatus": "needs_source"},
        "provenance": [],
        "createdAt": "2026-08-14T00:00:00Z",
        "updatedAt": "2026-08-14T00:00:00Z",
    }
    if allow_self_loop is not None:
        value["allowSelfLoop"] = allow_self_loop
    return value


def graph() -> dict[str, object]:
    return {
        "schemaVersion": "0.1",
        "documentId": "doc-1",
        "entities": [entity("e-1", tag="P-101"), entity("e-2", tag="V-101")],
        "connections": [connection()],
        "metadata": {"name": "Test graph", "sourceKind": "pid"},
    }


def assert_invalid(value: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        EngineeringGraph.model_validate(value)


def test_json_round_trip_preserves_canonical_field_names_and_values() -> None:
    original = graph()
    parsed = EngineeringGraph.model_validate_json(json.dumps(original))

    encoded = json.loads(
        parsed.model_dump_json(by_alias=True, exclude_none=True, exclude_defaults=True)
    )

    assert encoded == original
    assert parsed.entities[0].assertion.mode == "observed"
    assert parsed.entities[0].assertion.review_status == "unreviewed"
    assert parsed.entities[0].provenance[0].source_type == "page_image"


@pytest.mark.parametrize(
    ("collection", "object_name"), [("entities", "entity"), ("connections", "connection")]
)
def test_duplicate_ids_are_rejected(collection: str, object_name: str) -> None:
    value = graph()
    items = value[collection]
    assert isinstance(items, list)
    items.append(deepcopy(items[0]))

    assert_invalid(value, f"duplicate {object_name} IDs")


@pytest.mark.parametrize(
    ("field", "missing_id"), [("sourceEntityId", "missing-source"), ("targetEntityId", "missing-target")]
)
def test_missing_connection_references_are_rejected(field: str, missing_id: str) -> None:
    value = graph()
    connections = value["connections"]
    assert isinstance(connections, list)
    connections[0][field] = missing_id

    assert_invalid(value, f"missing {field.removesuffix('EntityId')} entity")


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_entity_confidence_outside_normalized_range_is_rejected(confidence: float) -> None:
    value = graph()
    entities = value["entities"]
    assert isinstance(entities, list)
    entities[0]["confidence"] = confidence

    assert_invalid(value, "Input should be")


def test_geometry_outside_range_is_rejected() -> None:
    value = graph()
    entities = value["entities"]
    assert isinstance(entities, list)
    entities[0]["geometry"] = {"polygon": [{"x": 1.1, "y": 0.5}]}

    assert_invalid(value, "less than or equal to 1")


def test_bbox_extent_outside_page_is_rejected() -> None:
    value = graph()
    entities = value["entities"]
    assert isinstance(entities, list)
    entities[0]["geometry"] = {"bbox": {"x": 0.9, "y": 0.2, "width": 0.2, "height": 0.2}}

    assert_invalid(value, "bounding box must remain")


def test_self_loop_requires_explicit_permission() -> None:
    value = graph()
    value["connections"] = [connection(source="e-1", target="e-1")]
    assert_invalid(value, "self-loop without allowSelfLoop=true")


def test_explicitly_allowed_self_loop_is_valid() -> None:
    value = graph()
    value["connections"] = [
        connection(source="e-1", target="e-1", allow_self_loop=True)
    ]

    parsed = EngineeringGraph.model_validate(value)

    assert parsed.connections[0].allow_self_loop is True


def test_duplicate_tags_produce_warning_without_rejecting_graph() -> None:
    value = graph()
    entities = value["entities"]
    assert isinstance(entities, list)
    entities[1]["tag"] = "P-101"

    parsed = EngineeringGraph.model_validate(value)
    warnings = duplicate_tag_warnings(parsed)

    assert warnings == [
        warnings[0].__class__(
            code="duplicate_tag",
            message="tag 'P-101' is used by multiple entities",
            entity_ids=("e-1", "e-2"),
        )
    ]


def test_properties_only_accept_json_values() -> None:
    value = graph()
    entities = value["entities"]
    assert isinstance(entities, list)
    entities[0]["properties"] = {"notJson": object()}

    assert_invalid(value, "validation error")

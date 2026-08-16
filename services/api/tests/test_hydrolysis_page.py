import json
from pathlib import Path

from app.benchmarks.hydrolysis_page import (
    GEOMETRY_STATUS,
    SOURCE_FILENAME,
    build_benchmark_inventory,
    build_page_fixture,
    write_page_fixture,
)

ROOT = Path(__file__).resolve().parents[3]
GRAPH = ROOT / "benchmarks/hydrolysis/expected/engineering_graph.json"
IMAGE = ROOT / "benchmarks/hydrolysis/images/IMG_6807.JPG"
IMAGES = ROOT / "benchmarks/hydrolysis/images"


def test_real_page_fixture_uses_dimensions_and_only_explicit_provenance() -> None:
    fixture = build_page_fixture(GRAPH, IMAGE)
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    expected_entities = {
        item["id"] for item in graph["entities"]
        if any(e["sourceRef"] == SOURCE_FILENAME for e in item["provenance"])
    }
    expected_connections = {
        item["id"] for item in graph["connections"]
        if any(e["sourceRef"] == SOURCE_FILENAME for e in item["provenance"])
    }
    assert (fixture["widthPx"], fixture["heightPx"]) == (5712, 4284)
    assert set(fixture["linkedEntityIds"]) == expected_entities
    assert set(fixture["linkedConnectionIds"]) == expected_connections
    assert fixture["counts"]["instruments"] == 43
    assert fixture["multiSourceObjectIds"]


def test_page_fixture_has_no_fabricated_geometry_and_is_deterministic(tmp_path: Path) -> None:
    first = build_page_fixture(GRAPH, IMAGE)
    second = build_page_fixture(GRAPH, IMAGE)
    assert first == second
    assert first["geometryCoverage"]["totalObjectsWithVerifiedGeometry"] == 0
    assert all(item["geometryStatus"] == GEOMETRY_STATUS for item in first["objects"])
    assert all("geometry" not in item for item in first["objects"])
    output = tmp_path / "page.json"
    write_page_fixture(first, output)
    before = output.read_bytes()
    write_page_fixture(second, output)
    assert output.read_bytes() == before


def test_all_provenance_linked_pages_generate_with_explicit_splits_and_zero_geometry() -> None:
    fixtures, inventory = build_benchmark_inventory(GRAPH, sorted(IMAGES.glob("IMG_*.JPG")))

    assert [fixture["sourceFilename"] for fixture in fixtures] == [
        f"IMG_{number}.JPG" for number in range(6806, 6815)
    ]
    assert inventory["splits"]["dev"] == ["IMG_6807.JPG"]
    assert inventory["splits"]["holdout"] == [
        "IMG_6806.JPG",
        *[f"IMG_{number}.JPG" for number in range(6808, 6815)],
    ]
    assert all(fixture["counts"]["entities"] > 0 for fixture in fixtures)
    assert all(
        fixture["geometryCoverage"]["totalObjectsWithVerifiedGeometry"] == 0
        for fixture in fixtures
    )
    assert all("geometry" not in item for fixture in fixtures for item in fixture["objects"])


def test_multi_page_generation_is_byte_stable(tmp_path: Path) -> None:
    first, first_inventory = build_benchmark_inventory(GRAPH, sorted(IMAGES.glob("IMG_*.JPG")))
    second, second_inventory = build_benchmark_inventory(GRAPH, sorted(IMAGES.glob("IMG_*.JPG")))

    assert first == second
    assert first_inventory == second_inventory
    for fixture in first:
        output = tmp_path / f"{Path(fixture['sourceFilename']).stem}.page.json"
        write_page_fixture(fixture, output)
        before = output.read_bytes()
        matching = next(item for item in second if item["sourceFilename"] == fixture["sourceFilename"])
        write_page_fixture(matching, output)
        assert output.read_bytes() == before

from pathlib import Path

from openpyxl import Workbook

from app.benchmarks.hydrolysis import (
    DOCUMENT_ID,
    FIXTURE_TIMESTAMP,
    UNASSIGNED_PAGE_ID,
    convert_workbook,
    write_conversion,
)


def test_actual_workbook_conversion_is_valid_deterministic_and_has_no_geometry() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    workbook = next((repository_root / "benchmarks/hydrolysis/reference").glob("*.xlsx"))
    first = convert_workbook(workbook)
    second = convert_workbook(workbook)

    assert first.graph.model_dump(mode="json", by_alias=True) == second.graph.model_dump(
        mode="json", by_alias=True
    )
    assert first.report == second.report
    assert first.graph.document_id == DOCUMENT_ID
    assert all(entity.page_id == UNASSIGNED_PAGE_ID for entity in first.graph.entities)
    assert all(entity.created_at == FIXTURE_TIMESTAMP for entity in first.graph.entities)
    assert all(entity.geometry is None for entity in first.graph.entities)
    assert all(connection.geometry is None for connection in first.graph.connections)


def test_maps_entities_connections_ownership_uncertainty_and_provenance(tmp_path: Path) -> None:
    result = convert_workbook(_fixture_workbook(tmp_path))
    graph = result.graph

    equipment = next(entity for entity in graph.entities if entity.id.endswith(":N_EQ1"))
    boundary = next(entity for entity in graph.entities if entity.id.endswith(":BND_IN"))
    instrument = next(entity for entity in graph.entities if entity.id.endswith(":I1"))
    assert equipment.kind == "equipment"
    assert equipment.subtype == "Pump"
    assert equipment.tag == "DUP-TAG"
    assert equipment.confidence == 0.8
    assert equipment.assertion.review_status == "needs_source"
    assert boundary.kind == "boundary"
    assert instrument.kind == "instrument"
    assert instrument.properties["unit"] == "°C"
    assert any(item.source_ref == "IMG_0001.JPG" for item in instrument.provenance)

    process = next(item for item in graph.connections if item.id.endswith(":C1"))
    utility = next(item for item in graph.connections if item.id.endswith(":C2"))
    ownership = next(item for item in graph.connections if item.kind == "ownership")
    assert process.kind == "process"
    assert utility.kind == "utility"
    assert process.geometry is None
    assert ownership.source_entity_id == instrument.id
    assert ownership.target_entity_id == equipment.id
    assert ownership.direction == "source_to_target"
    assert ownership.confidence == instrument.confidence
    assert ownership.assertion.review_status == "needs_source"

    assert result.report["brokenSourceTargetReferences"][0]["sourceConnectionId"] == "C3"
    assert result.report["missingInstrumentOwners"] == [{"sourceInstrumentId": "I2"}]
    assert result.report["brokenInstrumentOwnerReferences"][0]["sourceInstrumentId"] == "I3"
    assert result.report["duplicateTagWarnings"] == [{"tag": "DUP-TAG", "count": 2}]


def test_written_output_is_byte_stable(tmp_path: Path) -> None:
    result = convert_workbook(_fixture_workbook(tmp_path))
    output = tmp_path / "expected"
    write_conversion(result, output)
    first_graph = (output / "engineering_graph.json").read_bytes()
    first_report = (output / "import_report.json").read_bytes()
    write_conversion(result, output)
    assert (output / "engineering_graph.json").read_bytes() == first_graph
    assert (output / "import_report.json").read_bytes() == first_report


def _fixture_workbook(tmp_path: Path) -> Path:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for index in range(7):
        workbook.create_sheet(f"sheet-{index}")
    equipment = workbook.worksheets[4]
    connections = workbook.worksheets[5]
    instruments = workbook.worksheets[6]
    for sheet in (equipment, connections, instruments):
        sheet.append(["title"])
        sheet.append(["description"])
        sheet.append([])
        sheet.append(["headers"])
    equipment.append(["N_EQ1", "H01", "DUP-TAG", "Pump one", "Pump", None, None, None, "IMG_0001.JPG", "DCS visible", 0.8, "待现场核实", "check"])
    equipment.append(["BND_IN", "H01", None, "Feed boundary", "Boundary", None, None, None, "IMG_0001.JPG", "DCS boundary text", 0.7, "待现场核实", None])
    equipment.append(["N_EQ2", "H01", "DUP-TAG", "Pump two", "Pump", None, None, None, "IMG_0002.JPG", "DCS visible", 0.9, "已确认", None])
    connections.append(["C1", "H01", "BND_IN", "N_EQ1", "slurry", "Process", "IMG_0001.JPG", "DCS line", 0.6, "待现场核实", None])
    connections.append(["C2", "H01", "N_EQ1", "N_EQ2", "water", "Utility", "IMG_0001.JPG", "DCS line", 0.7, "待现场核实", None])
    connections.append(["C3", "H01", "MISSING", "N_EQ2", "water", "Process", "IMG_0001.JPG", "inferred", 0.3, "待现场核实", None])
    instruments.append(["I1", "H01", "TE-1", "Temperature", "N_EQ1", "°C", "measurement", "IMG_0001.JPG", "DCS visible", 0.75, "待现场核实", "candidate"])
    instruments.append(["I2", "H01", "FI-1", "Flow", None, "m3/h", "measurement", "IMG_0002.JPG", "DCS visible", 0.5, "待现场核实", None])
    instruments.append(["I3", "H01", "PI-1", "Pressure", "NO_NODE", "MPa", "measurement", "IMG_0002.JPG", "DCS visible", 0.4, "待现场核实", None])
    path = tmp_path / "fixture.xlsx"
    workbook.save(path)
    return path

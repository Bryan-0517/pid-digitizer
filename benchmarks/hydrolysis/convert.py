#!/usr/bin/env python3
from pathlib import Path

from app.benchmarks.hydrolysis import convert_workbook, write_conversion
from app.benchmarks.hydrolysis_page import build_page_fixture, write_page_fixture


def main() -> None:
    root = Path(__file__).resolve().parent
    workbook = next((root / "reference").glob("*.xlsx"))
    result = convert_workbook(workbook)
    write_conversion(result, root / "expected")
    page = build_page_fixture(
        root / "expected/engineering_graph.json", root / "images/IMG_6807.JPG"
    )
    write_page_fixture(page, root / "expected/pages/IMG_6807.page.json")
    print(f"Entities: {result.report['entityCount']}")
    print(f"Connections: {result.report['connectionCount']}")
    print(f"Instruments: {result.report['instrumentCount']}")
    print(f"Ownership connections: {result.report['ownershipConnectionsCreated']}")
    print(f"IMG_6807 page: {page['widthPx']}x{page['heightPx']}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from pathlib import Path

from app.benchmarks.hydrolysis import convert_workbook, write_conversion


def main() -> None:
    root = Path(__file__).resolve().parent
    workbook = next((root / "reference").glob("*.xlsx"))
    result = convert_workbook(workbook)
    write_conversion(result, root / "expected")
    print(f"Entities: {result.report['entityCount']}")
    print(f"Connections: {result.report['connectionCount']}")
    print(f"Instruments: {result.report['instrumentCount']}")
    print(f"Ownership connections: {result.report['ownershipConnectionsCreated']}")


if __name__ == "__main__":
    main()

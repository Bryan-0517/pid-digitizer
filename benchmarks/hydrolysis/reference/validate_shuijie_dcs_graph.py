#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate the pre-DEXPI hydrolysis DCS JSON and re-export tabular CSV files."""
from pathlib import Path
import json, csv
from collections import Counter

ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT / "钛一_水解DCS流程图_初步结构化.json"
OUT_DIR = ROOT / "shuijie_dcs_tabular_export_check"
OUT_DIR.mkdir(exist_ok=True)

def dump_csv(file_name, records):
    if not records:
        return
    headers = list(records[0].keys())
    with open(OUT_DIR / file_name, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(records)

def main():
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    nodes = payload["equipment_nodes"]
    node_ids = {x["node_id"] for x in nodes}
    tags = [x["dcs_tag"] for x in nodes if x.get("dcs_tag")]
    dup_tags = {tag: n for tag, n in Counter(tags).items() if n > 1}

    broken_conn = [
        x["connection_id"] for x in payload["process_connections"]
        if x["from_node_id"] not in node_ids or x["to_node_id"] not in node_ids
    ]
    broken_instruments = [
        x["instrument_id"] for x in payload["instrument_register"]
        if x["owner_node_id"] and x["owner_node_id"] not in node_ids
    ]

    print(f"Nodes: {len(nodes)}")
    print(f"Connections: {len(payload['process_connections'])}")
    print(f"Instruments: {len(payload['instrument_register'])}")
    print(f"Duplicate equipment tags: {dup_tags or 'None'}")
    print(f"Broken connection references: {broken_conn or 'None'}")
    print(f"Broken instrument owner references: {broken_instruments or 'None'}")

    mapping = {
        "areas.csv": payload["areas"],
        "screens.csv": payload["screens"],
        "equipment.csv": payload["equipment_nodes"],
        "connections.csv": payload["process_connections"],
        "instruments.csv": payload["instrument_register"],
        "operation_stages.csv": payload["operation_stages"],
        "ai_variables.csv": payload["ai_variable_map"],
        "control_points.csv": payload["control_points"],
        "validation_register.csv": payload["validation_register"],
        "dexpi_field_gap_register.csv": payload["dexpi_field_gap_register"],
    }
    for name, records in mapping.items():
        dump_csv(name, records)
    print(f"CSV export directory: {OUT_DIR}")

if __name__ == "__main__":
    main()

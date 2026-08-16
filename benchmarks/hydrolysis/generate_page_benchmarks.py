import argparse
import json
from pathlib import Path

from app.benchmarks.hydrolysis_page import build_benchmark_inventory, write_page_fixture


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate provenance-only hydrolysis page benchmarks")
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--images-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    fixtures, inventory = build_benchmark_inventory(
        args.graph, sorted(args.images_dir.glob("IMG_*.JPG"))
    )
    for fixture in fixtures:
        write_page_fixture(
            fixture, args.output_dir / f"{Path(fixture['sourceFilename']).stem}.page.json"
        )
    inventory_path = args.output_dir / "benchmark_inventory.json"
    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Generated {len(fixtures)} usable page fixtures")


if __name__ == "__main__":
    main()

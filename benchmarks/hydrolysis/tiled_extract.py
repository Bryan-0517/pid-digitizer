import argparse
import asyncio
from pathlib import Path

from app.ai.factory import create_ai_provider
from app.ai.tiled_extraction import PixelRegion, run_tiled_extraction
from app.config import settings


IMG_6807_PROCESS_DISPLAY_ROI = PixelRegion(x=96, y=636, width=4864, height=2748)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one fixed tiled IMG_6807 extraction experiment")
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=Path(__file__).parent / "evaluations" / "runs",
    )
    args = parser.parse_args()
    checkpoint_dir = args.runs_dir / args.experiment_id
    asyncio.run(
        run_tiled_extraction(
            provider=create_ai_provider(settings),
            image_path=args.image,
            experiment_id=args.experiment_id,
            benchmark_document_id="benchmark:hydrolysis",
            benchmark_page_id="benchmark:hydrolysis:IMG_6807.JPG",
            roi=IMG_6807_PROCESS_DISPLAY_ROI,
            maximum_output_tokens=6000,
            checkpoint_dir=checkpoint_dir,
            final_output_path=args.output,
        )
    )


if __name__ == "__main__":
    main()

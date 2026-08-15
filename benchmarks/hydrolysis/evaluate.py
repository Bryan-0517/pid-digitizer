import argparse
import json
from pathlib import Path

from app.ai.entity_proposals import EntityExtractionProposal
from app.ai.topology_proposals import TopologyExtractionProposal
from app.digitization.schemas import DigitizationProposalResponse
from app.evaluation import evaluate_img_6807, render_summary
from app.evaluation.schemas import EvaluationProviderMetadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a validated IMG_6807 proposal snapshot")
    parser.add_argument("proposal", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    payload = json.loads(args.proposal.read_text(encoding="utf-8"))
    if "entities" in payload:
        snapshot = DigitizationProposalResponse.model_validate(payload)
        proposal = snapshot.entities
        topology = snapshot.topology
        metadata = EvaluationProviderMetadata(
            provider=snapshot.entity_provider_metadata.provider,
            model=snapshot.entity_provider_metadata.model,
            request_id=snapshot.entity_provider_metadata.request_id,
            latency_ms=snapshot.entity_provider_metadata.latency_ms,
            usage=snapshot.entity_provider_metadata.usage,
        )
    else:
        proposal = EntityExtractionProposal.model_validate(payload)
        topology = TopologyExtractionProposal(connections=[], warnings=[])
        metadata = None
    result = evaluate_img_6807(
        proposal=proposal,
        topology=topology,
        run_id=args.run_id,
        provider_metadata=metadata,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        result.model_dump_json(by_alias=True, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(render_summary(result))


if __name__ == "__main__":
    main()

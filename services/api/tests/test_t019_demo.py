import importlib.util
import json
from pathlib import Path

from app.graph_queries.schemas import NeighborsQuery
from app.graph_queries.service import GraphQueryService


ROOT = Path(__file__).parents[3]
MANIFEST = ROOT / "demo/t019-manifest.json"
PROPOSAL = ROOT / "benchmarks/hydrolysis/evaluations/fixtures/IMG_6807.openai-gpt5.tiled-20260816-02-validation-v1.proposal.json"
IMAGE = ROOT / "benchmarks/hydrolysis/images/IMG_6807.JPG"
HELPER = ROOT / "services/api/demo/t019_demo.py"

spec = importlib.util.spec_from_file_location("t019_demo_helper", HELPER)
if spec is None or spec.loader is None:
    raise RuntimeError(f"could not load T019 demo helper from {HELPER}")
t019_demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t019_demo)
build_graph = t019_demo.build_graph
load_and_validate_assets = t019_demo.load_and_validate_assets


def test_saved_proposal_and_manifest_preserve_provenance_boundaries() -> None:
    manifest, proposal = load_and_validate_assets(MANIFEST, PROPOSAL, IMAGE)
    assert proposal["topologyProposalCount"] == 0
    assert manifest["connections"][0]["modelTopologyCandidateId"] is None
    graph = build_graph(manifest, "document", "page")
    assert len(graph.entities) == 2
    assert {(item.id, item.tag, item.kind, item.subtype) for item in graph.entities} == {
        ("t019:entity:fi-0828", "FI_0828", "instrument", None),
        ("t019:entity:fv-0827", "FV_0827", "valve", "FV"),
    }
    assert {item["proposalCandidateId"] for item in manifest["entities"]} == {
        "instruments:r1c0:inst-3", "valves:r1c0:valve-7",
    }
    assert all(item.assertion.mode == "inferred" for item in graph.entities)
    assert all(item.assertion.review_status == "unreviewed" for item in graph.entities)
    assert all(item.confidence is None for item in graph.entities)
    assert all(item.provenance[0].source_type == "model" for item in graph.entities)
    connection = graph.connections[0]
    assert connection.id == "t019:connection:fi-0828--fv-0827"
    assert connection.kind == "reference"
    assert connection.direction == "unknown"
    assert connection.geometry is None and connection.confidence is None
    assert connection.assertion.mode == "human_added"
    assert connection.assertion.review_status == "confirmed"
    assert connection.provenance[0].source_type == "human"
    assert "not model output" in connection.provenance[0].note
    assert "not derived from benchmark truth" in connection.provenance[0].note
    assert "not process flow" in connection.provenance[0].note
    assert "formal control-loop" in connection.provenance[0].note


def test_demo_graph_has_only_the_approved_undirected_neighbor_result() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    graph = build_graph(manifest, "document", "page")
    service = GraphQueryService()
    result = service.query(graph, NeighborsQuery(
        operation="neighbors", entity_id="t019:entity:fi-0828"))
    assert result.entity_ids == ["t019:entity:fv-0827"]
    assert result.connection_ids == ["t019:connection:fi-0828--fv-0827"]

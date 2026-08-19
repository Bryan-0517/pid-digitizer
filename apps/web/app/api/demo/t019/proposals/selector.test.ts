import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test } from "vitest";
import { selectProposalOverlays, verifiedProposalCandidateIds } from "./selector";

const snapshotPath = path.resolve(process.cwd(), "../../benchmarks/hydrolysis/evaluations/fixtures/IMG_6807.openai-gpt5.tiled-20260816-02-validation-v1.proposal.json");

test("selects the fixed IMG_6807 proposal-only presentation set deterministically", () => {
  const snapshot = JSON.parse(readFileSync(snapshotPath, "utf8")) as {
    mergedProposal: { candidates: Parameters<typeof selectProposalOverlays>[0] };
  };
  const selected = selectProposalOverlays(snapshot.mergedProposal.candidates);

  expect(selected.map((candidate) => candidate.candidateId)).toEqual(verifiedProposalCandidateIds);
  expect(selected).toHaveLength(8);
  expect(selected.every((candidate) => candidate.geometry.bbox.width > 0
    && candidate.geometry.bbox.height > 0)).toBe(true);
  expect(selected.map((candidate) => candidate.tag)).not.toContain("FI_0828");
  expect(selected.map((candidate) => candidate.tag)).not.toContain("FV_0827");
});

test("does not substitute geometric lookalikes when a reviewed candidate is absent", () => {
  const selected = selectProposalOverlays([{
    candidateId: "unreviewed-lookalike", kind: "equipment", tag: "LOOKALIKE",
    geometry: { bbox: { x: 0.1, y: 0.1, width: 0.2, height: 0.2 } },
  }]);
  expect(selected).toEqual([]);
});

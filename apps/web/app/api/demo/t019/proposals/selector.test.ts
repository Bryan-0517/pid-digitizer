import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test } from "vitest";
import { selectProposalOverlays } from "./selector";

const snapshotPath = path.resolve(process.cwd(), "../../benchmarks/hydrolysis/evaluations/fixtures/IMG_6807.openai-gpt5.tiled-20260816-02-validation-v1.proposal.json");

test("selects the fixed IMG_6807 proposal-only presentation set deterministically", () => {
  const snapshot = JSON.parse(readFileSync(snapshotPath, "utf8")) as {
    mergedProposal: { candidates: Parameters<typeof selectProposalOverlays>[0] };
  };
  const selected = selectProposalOverlays(snapshot.mergedProposal.candidates);

  expect(selected.map((candidate) => candidate.candidateId)).toEqual([
    "equipment_boundary:r0c0:cand-2",
    "instruments:r1c0:inst-5",
    "equipment_boundary:r0c0:cand-6",
    "instruments:r1c0:inst-10",
    "equipment_boundary:r0c1:eq4",
    "equipment_boundary:r1c1:eq-A310002D-tank",
    "equipment_boundary:r0c1:eq7",
    "equipment_boundary:r1c1:eq-A310002G-tank",
  ]);
  expect(selected).toHaveLength(8);
  expect(selected.every((candidate) => candidate.geometry.bbox.width >= 0.02
    && candidate.geometry.bbox.height >= 0.02)).toBe(true);
  expect(selected.map((candidate) => candidate.tag)).not.toContain("TV_0806B");
  expect(selected.map((candidate) => candidate.tag)).not.toContain("A310001B");
});

import { readFile } from "node:fs/promises";
import path from "node:path";
import { NextResponse } from "next/server";
import type { DemoProposalOverlayResponse } from "../../../../../types/proposal-overlay";
import { selectProposalOverlays } from "./selector";

const snapshotPath = path.resolve(process.cwd(), "../../benchmarks/hydrolysis/evaluations/fixtures/IMG_6807.openai-gpt5.tiled-20260816-02-validation-v1.proposal.json");

export async function GET() {
  const snapshot = JSON.parse(await readFile(snapshotPath, "utf8")) as {
    snapshotLabel: string;
    sourceFilename: string;
    mergedProposal?: { candidates?: Parameters<typeof selectProposalOverlays>[0] };
  };
  const response: DemoProposalOverlayResponse = {
    snapshotLabel: snapshot.snapshotLabel,
    sourceFilename: snapshot.sourceFilename,
    candidates: selectProposalOverlays(snapshot.mergedProposal?.candidates ?? []),
  };
  return NextResponse.json(response, {
    headers: { "Cache-Control": "public, max-age=3600, immutable" },
  });
}

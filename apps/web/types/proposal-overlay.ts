import type { BoundingBox } from "./engineering-graph";

export type ProposalOverlayCandidate = {
  candidateId: string;
  kind: "equipment" | "valve" | "instrument" | "boundary";
  subtype?: string | null;
  tag?: string | null;
  displayName?: string | null;
  geometry: { bbox: BoundingBox };
};

export type DemoProposalOverlayResponse = {
  snapshotLabel: string;
  sourceFilename: string;
  candidates: ProposalOverlayCandidate[];
};

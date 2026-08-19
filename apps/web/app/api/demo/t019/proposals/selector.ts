import type { ProposalOverlayCandidate } from "../../../../../types/proposal-overlay";

type SnapshotCandidate = Partial<ProposalOverlayCandidate> & {
  candidateId?: string;
  kind?: string;
  geometry?: { bbox?: Partial<ProposalOverlayCandidate["geometry"]["bbox"]> | null } | null;
};

const canonicalCandidateIds = new Set(["instruments:r1c0:inst-3", "valves:r1c0:valve-7"]);
const canonicalTags = new Set(["FI_0828", "FV_0827"]);

// Each stored bbox in this fixed presentation allowlist was visually checked against IMG_6807.
// Selection is deliberately not inferred from box size, score, or page distribution.
export const verifiedProposalCandidateIds = [
  "equipment_boundary:r0c0:cand-1",
  "equipment_boundary:r0c0:cand-6",
  "equipment_boundary:r0c0:cand-7",
  "equipment_boundary:r1c1:bdry-top-header",
  "equipment_boundary:r1c1:bdry-inlet-D",
  "equipment_boundary:r1c1:bdry-inlet-F",
  "equipment_boundary:r1c1:bdry-inlet-G",
  "equipment_boundary:r1c1:bdry-bottom-header",
] as const;

export function selectProposalOverlays(candidates: SnapshotCandidate[]): ProposalOverlayCandidate[] {
  const byId = new Map<string, ProposalOverlayCandidate>();
  for (const raw of candidates) {
    const candidate = normalizedCandidate(raw);
    if (!candidate || canonicalCandidateIds.has(candidate.candidateId)
      || (candidate.tag ? canonicalTags.has(candidate.tag) : false)) continue;
    const box = candidate.geometry.bbox;
    if (box.x < 0 || box.y < 0 || box.x + box.width > 1 || box.y + box.height > 1
      || box.width <= 0 || box.height <= 0) continue;
    byId.set(candidate.candidateId, candidate);
  }
  return verifiedProposalCandidateIds.flatMap((candidateId) => {
    const candidate = byId.get(candidateId);
    return candidate ? [candidate] : [];
  });
}

function normalizedCandidate(raw: SnapshotCandidate): ProposalOverlayCandidate | null {
  const box = raw.geometry?.bbox;
  if (!raw.candidateId || !isKind(raw.kind) || !box
    || !isFiniteNumber(box.x) || !isFiniteNumber(box.y)
    || !isFiniteNumber(box.width) || !isFiniteNumber(box.height)) return null;
  return {
    candidateId: raw.candidateId,
    kind: raw.kind,
    subtype: clean(raw.subtype), tag: clean(raw.tag), displayName: clean(raw.displayName),
    geometry: { bbox: { x: box.x, y: box.y, width: box.width, height: box.height } },
  };
}

function isKind(value: string | undefined): value is ProposalOverlayCandidate["kind"] {
  return value === "equipment" || value === "valve" || value === "instrument" || value === "boundary";
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function clean(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed || null;
}

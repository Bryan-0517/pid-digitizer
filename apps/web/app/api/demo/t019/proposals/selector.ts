import type { ProposalOverlayCandidate } from "../../../../../types/proposal-overlay";

type SnapshotCandidate = Partial<ProposalOverlayCandidate> & {
  candidateId?: string;
  kind?: string;
  geometry?: { bbox?: Partial<ProposalOverlayCandidate["geometry"]["bbox"]> | null } | null;
};

const canonicalCandidateIds = new Set(["valves:r0c1:valve-1", "equipment_boundary:r0c1:eq1"]);
const canonicalTags = new Set(["TV_0806B", "A310001B"]);
const kindRank: Record<ProposalOverlayCandidate["kind"], number> = {
  equipment: 4, valve: 3, instrument: 2, boundary: 1,
};

export function selectProposalOverlays(candidates: SnapshotCandidate[]): ProposalOverlayCandidate[] {
  const cells = new Map<string, { candidate: ProposalOverlayCandidate; score: number }>();
  for (const raw of candidates) {
    const candidate = normalizedCandidate(raw);
    if (!candidate || canonicalCandidateIds.has(candidate.candidateId)
      || (candidate.tag ? canonicalTags.has(candidate.tag) : false)) continue;
    const box = candidate.geometry.bbox;
    const area = box.width * box.height;
    if (box.x < 0 || box.y < 0 || box.x + box.width > 1 || box.y + box.height > 1
      || box.width < 0.02 || box.height < 0.02 || area < 0.0003 || area > 0.025) continue;

    const column = Math.min(3, Math.floor((box.x + box.width / 2) * 4));
    const row = Math.min(2, Math.floor((box.y + box.height / 2) * 3));
    const cell = `${column}:${row}`;
    const score = kindRank[candidate.kind] + (candidate.tag ? 2 : 0)
      + (candidate.displayName?.trim() ? 0.5 : 0) - Math.abs(Math.log(area / 0.002));
    const current = cells.get(cell);
    if (!current || score > current.score
      || (score === current.score && candidate.candidateId < current.candidate.candidateId)) {
      cells.set(cell, { candidate, score });
    }
  }
  return [...cells.entries()].sort(([left], [right]) => left.localeCompare(right))
    .map(([, item]) => item.candidate).slice(0, 8);
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

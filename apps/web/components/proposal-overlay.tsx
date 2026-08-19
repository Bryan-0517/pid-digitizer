import React from "react";
import { Layer, Rect } from "react-konva";
import type { ProposalOverlayCandidate } from "../types/proposal-overlay";
import { normalizedBboxToImage } from "./graph-geometry";

type Props = {
  candidates: ProposalOverlayCandidate[];
  imageSize: { width: number; height: number };
  viewScale: number;
};

export default function ProposalOverlay({ candidates, imageSize, viewScale }: Props) {
  const strokeWidth = 2.25 / viewScale;
  return <Layer name="proposals" listening={false}>
    {candidates.map((candidate) => {
      const box = normalizedBboxToImage(candidate.geometry.bbox, imageSize);
      return <Rect key={candidate.candidateId} {...box} name="proposal-rect"
        fill="rgba(249, 115, 22, 0.08)" stroke="#f97316" strokeWidth={strokeWidth}
        dash={[8 / viewScale, 5 / viewScale]} opacity={0.92} listening={false} />;
    })}
  </Layer>;
}

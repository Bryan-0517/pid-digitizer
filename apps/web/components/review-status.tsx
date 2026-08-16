import React from "react";
import type { Assertion } from "../types/engineering-graph";

export default function ReviewStatus({ confidence, assertion }: { confidence?: number; assertion: Assertion }) {
  return <dl className="canonical-status" aria-label="Canonical confidence and review metadata">
    <dt>Confidence</dt><dd>{confidence ?? "Not provided"}</dd>
    <dt>Review status</dt><dd><span className={`status-badge review-${assertion.reviewStatus}`}>{assertion.reviewStatus}</span></dd>
    <dt>Assertion mode</dt><dd><span className={`status-badge assertion-${assertion.mode}`}>{assertion.mode}</span></dd>
  </dl>;
}

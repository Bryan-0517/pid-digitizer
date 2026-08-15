import React from "react";
import type { EngineeringGraph } from "../types/engineering-graph";

export type BenchmarkPageFixture = {
  pageId: string;
  documentId: string;
  sourceFilename: string;
  widthPx: number;
  heightPx: number;
  linkedEntityIds: string[];
  linkedConnectionIds: string[];
  linkedInstrumentIds: string[];
  counts: { entities: number; connections: number; instruments: number; multiSourceObjects: number };
  geometryCoverage: { status: string; totalObjectsWithVerifiedGeometry: number };
  warnings: string[];
};

export default function BenchmarkSummary({ fixture, graph }: { fixture: BenchmarkPageFixture; graph: EngineeringGraph }) {
  const entityIds = new Set(fixture.linkedEntityIds);
  const connectionIds = new Set(fixture.linkedConnectionIds);
  const entities = graph.entities.filter(item => entityIds.has(item.id));
  const connections = graph.connections.filter(item => connectionIds.has(item.id));
  return <aside className="benchmark-summary">
    <h2>Hydrolysis benchmark reference</h2>
    <p><strong>Reference mode:</strong> pre-DEXPI material, not verified engineering truth.</p>
    <p>Verified geometry coverage: <strong>{fixture.geometryCoverage.totalObjectsWithVerifiedGeometry}</strong></p>
    <p>{fixture.counts.entities} entities · {fixture.counts.instruments} instruments · {fixture.counts.connections} connections</p>
    <p>All linked objects: {fixture.geometryCoverage.status}. No overlays are drawn.</p>
    <details><summary>Entities and instruments</summary><ul>{entities.map(item => <li key={item.id}>{item.tag ?? item.displayName ?? item.id} ({item.kind})</li>)}</ul></details>
    <details><summary>Connections</summary><ul>{connections.map(item => <li key={item.id}>{item.id} ({item.kind})</li>)}</ul></details>
    {fixture.warnings.map(warning => <p className="benchmark-warning" key={warning}>{warning}</p>)}
  </aside>;
}

import type { EngineeringEntity, EngineeringGraph } from "../types/engineering-graph";

const timestamp = "2026-08-15T00:00:00Z";

export function createMockEngineeringGraph(documentId: string, pageId: string): EngineeringGraph {
  const entity = (
    id: string,
    kind: EngineeringEntity["kind"],
    bbox: { x: number; y: number; width: number; height: number },
    label: { tag?: string; displayName?: string },
  ): EngineeringEntity => ({
    id,
    documentId,
    pageId,
    kind,
    ...label,
    properties: {},
    geometry: { bbox },
    assertion: { mode: "human_added", reviewStatus: "unreviewed" },
    provenance: [{
      id: `evidence-${id}`,
      sourceType: "human",
      sourceRef: "t004-mock-fixture",
      pageId,
      note: "Explicit mock geometry for the T004 overlay demonstration only.",
    }],
    createdAt: timestamp,
    updatedAt: timestamp,
  });

  return {
    schemaVersion: "0.1",
    documentId,
    metadata: {
      name: "T004 mock overlay",
      description: "Synthetic fixture geometry; not extracted or verified engineering truth.",
      sourceKind: "unknown",
    },
    entities: [
      entity("mock-equipment-1", "equipment", { x: 0.12, y: 0.24, width: 0.18, height: 0.22 }, { tag: "P-MOCK-1" }),
      entity("mock-valve-1", "valve", { x: 0.43, y: 0.42, width: 0.07, height: 0.10 }, { tag: "V-MOCK-1" }),
      entity("mock-instrument-1", "instrument", { x: 0.62, y: 0.18, width: 0.09, height: 0.12 }, { displayName: "Mock indicator" }),
      entity("mock-boundary-1", "boundary", { x: 0.82, y: 0.39, width: 0.10, height: 0.16 }, {}),
    ],
    connections: [
      {
        id: "mock-connection-with-geometry",
        documentId,
        sourceEntityId: "mock-equipment-1",
        targetEntityId: "mock-valve-1",
        kind: "process",
        direction: "source_to_target",
        geometry: { polyline: [{ x: 0.30, y: 0.35 }, { x: 0.38, y: 0.35 }, { x: 0.46, y: 0.42 }] },
        properties: {},
        assertion: { mode: "human_added", reviewStatus: "unreviewed" },
        provenance: [{ id: "evidence-mock-connection-1", sourceType: "human", sourceRef: "t004-mock-fixture", pageId }],
        createdAt: timestamp,
        updatedAt: timestamp,
      },
      {
        id: "mock-connection-without-geometry",
        documentId,
        sourceEntityId: "mock-valve-1",
        targetEntityId: "mock-boundary-1",
        kind: "process",
        properties: {},
        assertion: { mode: "human_added", reviewStatus: "unreviewed" },
        provenance: [{ id: "evidence-mock-connection-2", sourceType: "human", sourceRef: "t004-mock-fixture", pageId }],
        createdAt: timestamp,
        updatedAt: timestamp,
      },
    ],
  };
}

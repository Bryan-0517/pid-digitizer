import type { Assertion, EngineeringEntity, EvidenceRef } from "./engineering-graph";

export type ChatOutcome = "ok" | "not_found" | "clarification_required" | "unsupported" | "no_path";
export type ChatIntent = "neighbors" | "upstream" | "downstream" | "shortest_path" | "entity_lookup";

export type GraphQueryResult = {
  operation: ChatIntent;
  outcome: "ok" | "not_found" | "ambiguous" | "no_path";
  entityIds: string[];
  connectionIds: string[];
  paths: Array<{ entityIds: string[]; connectionIds: string[] }>;
  entities: EngineeringEntity[];
  connections: Array<{
    id: string;
    sourceEntityId: string;
    targetEntityId: string;
    kind: string;
    direction?: string;
    assertion: Assertion;
    provenance: EvidenceRef[];
    confidence?: number;
  }>;
};

export type ChatWarning = {
  code: "uncertain_entity" | "uncertain_connection" | "verbalization_failed";
  message: string;
  objectType?: "entity" | "connection";
  objectId?: string;
  assertion?: Assertion;
  confidence?: number;
  provenance: EvidenceRef[];
  connectionKind?: string;
  originalDirection?: string;
};

export type ChatResponse = {
  outcome: ChatOutcome;
  resolvedIntent?: { operation: ChatIntent; references: string[]; resolvedEntityIds: string[] };
  queryResults: GraphQueryResult[];
  answer: string;
  supportingEntityIds: string[];
  supportingConnectionIds: string[];
  highlight: { entityIds: string[]; connectionIds: string[] };
  warnings: ChatWarning[];
  verbalizationMetadata?: { provider: string; model: string };
};

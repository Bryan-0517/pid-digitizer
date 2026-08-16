import type { Assertion, JsonValue } from "./engineering-graph";

export type FieldDisposition = "supported" | "unmapped" | "blocked";
export type ObjectDisposition = "supported" | "partial" | "unmapped" | "blocked";

export type DexpiFieldReport = {
  path: string;
  disposition: FieldDisposition;
  reasonCode: string;
  message: string;
  value: JsonValue;
};

export type DexpiObjectReport = {
  objectType: "entity" | "connection";
  canonicalId: string;
  kind: string;
  label?: string;
  disposition: ObjectDisposition;
  assertion?: Assertion;
  suggestedClass?: string;
  originalMappingStatus?: string;
  fields: DexpiFieldReport[];
};

export type DexpiMappingReport = {
  boundaryVersion: "internal-v0.1";
  targetDexpiVersion: null;
  conformanceValidated: false;
  status: "supported" | "partial" | "blocked" | "empty";
  graphFields: DexpiFieldReport[];
  objects: DexpiObjectReport[];
  counts: {
    supportedObjects: number;
    partialObjects: number;
    unmappedObjects: number;
    blockedObjects: number;
    supportedFields: number;
    unmappedFields: number;
    blockedFields: number;
  };
  preview: {
    boundaryVersion: "internal-v0.1";
    targetDexpiVersion: null;
    conformant: false;
    objects: unknown[];
  };
  warnings: string[];
};

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

export type DexpiExportAvailability = {
  enabled: boolean;
  available: boolean;
  pydexpiVersion: "1.2.0";
  targetDexpiVersion: "1.3";
  artifactLabel: string;
  reason?: string;
};

export type DexpiConversionReport = {
  status: "ready" | "blocked" | "empty" | "no_exportable_content";
  pydexpiVersion: "1.2.0";
  targetDexpiVersion: "1.3";
  conformanceValidated: false;
  artifactLabel: string;
  includedObjects: Array<{ canonicalId: string; canonicalKind: string; pydexpiClass: string; convertedFieldPaths: string[] }>;
  omittedObjects: Array<{ canonicalId: string; objectType: "entity" | "connection"; canonicalKind: string; t015Disposition: string; reasonCode: string; message: string }>;
  omittedFields: Array<{ canonicalId: string; path: string; reasonCode: string; message: string }>;
  blockingObjects: Array<{ canonicalId: string; reasonCodes: string[] }>;
  warnings: string[];
};

export type PydexpiCompatibilityArtifact = {
  artifactLabel: string;
  conformanceValidated: false;
  conversionReport: DexpiConversionReport;
  pydexpiModel: unknown;
  pydexpiVersion: "1.2.0";
  targetDexpiVersion: "1.3";
};

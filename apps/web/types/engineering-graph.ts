export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

export type Point = { x: number; y: number };
export type BoundingBox = Point & { width: number; height: number };

export type GraphMetadata = {
  name?: string;
  description?: string;
  sourceKind?: "pid" | "pfd" | "hmi" | "dcs" | "unknown";
};

export type EvidenceRef = {
  id: string;
  sourceType: "page_image" | "ocr" | "model" | "spreadsheet" | "external_document" | "human";
  sourceRef: string;
  pageId?: string;
  region?: BoundingBox;
  rawText?: string;
  note?: string;
  confidence?: number;
};

export type Assertion = {
  mode: "observed" | "inferred" | "human_added";
  reviewStatus: "unreviewed" | "confirmed" | "corrected" | "rejected" | "needs_source";
};

export type EngineeringEntity = {
  id: string;
  documentId: string;
  pageId: string;
  kind: "equipment" | "valve" | "instrument" | "boundary" | "text" | "unknown";
  subtype?: string;
  tag?: string;
  displayName?: string;
  properties: Record<string, JsonValue>;
  geometry?: { bbox?: BoundingBox; polygon?: Point[]; anchorPoints?: Point[] };
  confidence?: number;
  assertion: Assertion;
  provenance: EvidenceRef[];
  dexpi?: {
    suggestedClass?: string;
    mappingStatus?: "not_checked" | "mappable" | "partial" | "blocked";
  };
  createdAt: string;
  updatedAt: string;
};

export type EngineeringConnection = {
  id: string;
  documentId: string;
  sourceEntityId: string;
  targetEntityId: string;
  allowSelfLoop?: boolean;
  kind: "process" | "utility" | "signal" | "ownership" | "reference" | "unknown";
  medium?: string;
  direction?: "source_to_target" | "target_to_source" | "undirected" | "unknown";
  geometry?: { polyline?: Point[] };
  properties: Record<string, JsonValue>;
  confidence?: number;
  assertion: Assertion;
  provenance: EvidenceRef[];
  createdAt: string;
  updatedAt: string;
};

export type EngineeringGraph = {
  schemaVersion: "0.1";
  documentId: string;
  entities: EngineeringEntity[];
  connections: EngineeringConnection[];
  metadata: GraphMetadata;
};

export type Document = {
  id: string;
  name: string;
  sourceType: "image" | "pdf";
  status: "uploaded" | "processing" | "ready" | "error";
  createdAt: string;
  updatedAt: string;
};

export type DocumentPage = {
  id: string;
  documentId: string;
  pageNumber: number;
  imageUri: string;
  widthPx: number;
  heightPx: number;
};

export type DigitizationJob = {
  id: string;
  documentId: string;
  status: "queued" | "running" | "succeeded" | "failed";
  provider: string;
  providerModel?: string;
  startedAt?: string;
  finishedAt?: string;
  warnings: string[];
  error?: string;
};

export type GraphRevision = {
  id: string;
  documentId: string;
  objectType: "entity" | "connection";
  objectId: string;
  operation: "create" | "update" | "delete";
  fieldPath?: string;
  before?: JsonValue;
  after?: JsonValue;
  actorType: "user" | "model" | "system";
  actorId?: string;
  createdAt: string;
};

# DATA_MODEL.md — EngineeringGraph v0.1

## 1. Canonical aggregate

```ts
type EngineeringGraph = {
  schemaVersion: "0.1";
  documentId: string;
  entities: EngineeringEntity[];
  connections: EngineeringConnection[];
  metadata: GraphMetadata;
};

type GraphMetadata = {
  name?: string;
  description?: string;
  sourceKind?: "pid" | "pfd" | "hmi" | "dcs" | "unknown";
};
```

## 2. Entity

```ts
type EngineeringEntity = {
  id: string;
  documentId: string;
  pageId: string;

  kind:
    | "equipment"
    | "valve"
    | "instrument"
    | "boundary"
    | "text"
    | "unknown";

  subtype?: string;
  tag?: string;
  displayName?: string;

  properties: Record<string, JsonValue>;

  geometry?: {
    bbox?: {
      x: number;      // normalized 0..1
      y: number;
      width: number;
      height: number;
    };
    polygon?: Array<{ x: number; y: number }>;
    anchorPoints?: Array<{ x: number; y: number }>;
  };

  confidence?: number;

  assertion: {
    mode: "observed" | "inferred" | "human_added";
    reviewStatus:
      | "unreviewed"
      | "confirmed"
      | "corrected"
      | "rejected"
      | "needs_source";
  };

  provenance: EvidenceRef[];

  dexpi?: {
    suggestedClass?: string;
    mappingStatus?: "not_checked" | "mappable" | "partial" | "blocked";
  };

  createdAt: string;
  updatedAt: string;
};
```

## 3. Connection

```ts
type EngineeringConnection = {
  id: string;
  documentId: string;

  sourceEntityId: string;
  targetEntityId: string;

  // Required only when this connection intentionally connects an entity to itself.
  // Absent means false.
  allowSelfLoop?: boolean;

  kind:
    | "process"
    | "utility"
    | "signal"
    | "ownership"
    | "reference"
    | "unknown";

  medium?: string;
  direction?: "source_to_target" | "target_to_source" | "undirected" | "unknown";

  geometry?: {
    polyline?: Array<{ x: number; y: number }>;
  };

  properties: Record<string, JsonValue>;
  confidence?: number;

  assertion: {
    mode: "observed" | "inferred" | "human_added";
    reviewStatus:
      | "unreviewed"
      | "confirmed"
      | "corrected"
      | "rejected"
      | "needs_source";
  };

  provenance: EvidenceRef[];

  createdAt: string;
  updatedAt: string;
};
```

Canonical ownership direction is instrument to owner: an ownership connection uses the instrument
as `sourceEntityId`, its owning equipment or boundary as `targetEntityId`, `kind="ownership"`, and
`direction="source_to_target"`. Reverse lookups such as “which instruments belong to this equipment?”
traverse incoming ownership edges.

## 4. Evidence

```ts
type EvidenceRef = {
  id: string;
  sourceType:
    | "page_image"
    | "ocr"
    | "model"
    | "spreadsheet"
    | "external_document"
    | "human";

  sourceRef: string;
  pageId?: string;
  region?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };

  rawText?: string;
  note?: string;
  confidence?: number;
};
```

Evidence is deliberately separate from the engineering property it supports.

## 5. Document

```ts
type Document = {
  id: string;
  name: string;
  sourceType: "image" | "pdf";
  status: "uploaded" | "processing" | "ready" | "error";
  createdAt: string;
  updatedAt: string;
};

type DocumentPage = {
  id: string;
  documentId: string;
  pageNumber: number;
  imageUri: string;
  widthPx: number;
  heightPx: number;
};
```

## 6. Digitization job

```ts
type DigitizationJob = {
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
```

## 7. Revision event

```ts
type GraphRevision = {
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
```

## 8. Hydrolysis benchmark adapter

The existing hydrolysis pre-DEXPI registers are not identical to EngineeringGraph. Import them through a benchmark adapter.

Initial mapping:

```text
equipment_nodes
    -> EngineeringEntity(kind = equipment/boundary)

instrument_register
    -> EngineeringEntity(kind = instrument)
       + optional ownership connection

process_connections
    -> EngineeringConnection(kind = process/utility)

screens
    -> DocumentPage/source metadata

confidence/status/source
    -> assertion + provenance
```

Do not copy benchmark uncertainty into `confirmed`.
Rows marked "待现场核实" remain unreviewed/needs_source.

## 9. Validation invariants

The domain validator must reject or flag:

- duplicate entity IDs;
- duplicate connection IDs;
- connection source/target referencing missing entities;
- self-loop unless the connection has `allowSelfLoop: true`;
- geometry outside normalized [0,1] range;
- invalid confidence outside [0,1];
- unsupported enum values;
- DEXPI export attempt for blocked/unreviewed required objects.

Duplicate tags are a warning, not always a hard error, because source material may itself be ambiguous.

## 10. Deliberate non-modeling in v0.1

Do not model these as first-class domain types yet:
- full ISA loop semantics;
- nozzle topology;
- pipe class/material/spec;
- line list;
- alarm/interlock/SIS cause-effect;
- full graphics primitives required by formal DEXPI.

Keep these in `properties` or explicit DEXPI-gap reports until the product earns a richer schema.

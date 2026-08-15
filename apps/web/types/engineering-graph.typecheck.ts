import type {
  DigitizationJob,
  Document,
  DocumentPage,
  EngineeringGraph,
  GraphRevision,
} from "./engineering-graph";

const graph = {
  schemaVersion: "0.1",
  documentId: "doc-1",
  entities: [],
  connections: [],
  metadata: { sourceKind: "pid" },
} satisfies EngineeringGraph;

const document = {
  id: "doc-1",
  name: "Example",
  sourceType: "image",
  status: "ready",
  createdAt: "2026-08-14T00:00:00Z",
  updatedAt: "2026-08-14T00:00:00Z",
} satisfies Document;

const page = {
  id: "page-1",
  documentId: document.id,
  pageNumber: 1,
  imageUri: "/example.png",
  widthPx: 100,
  heightPx: 100,
} satisfies DocumentPage;

const job = {
  id: "job-1",
  documentId: graph.documentId,
  status: "queued",
  provider: "fake",
  warnings: [],
} satisfies DigitizationJob;

const revision = {
  id: "revision-1",
  documentId: graph.documentId,
  objectType: "entity",
  objectId: "e-1",
  operation: "create",
  actorType: "system",
  createdAt: "2026-08-14T00:00:00Z",
} satisfies GraphRevision;

void [graph, document, page, job, revision];

# ARCHITECTURE.md — P&ID Digitizer v0.1

## 1. System shape

```text
Browser
  |
  v
Next.js Web App
  |  REST/JSON
  v
FastAPI Service
  |
  +-- Document service
  +-- Digitization service
  +-- EngineeringGraph service
  +-- Graph query service
  +-- DEXPI adapter
  |
  +-- PostgreSQL
  +-- Local file storage in development
```

## 2. Frontend

Recommended stack:
- Next.js + React + TypeScript.
- react-konva for the diagram canvas.
- A normal React inspector panel for editing.
- TanStack Query or equivalent for server state; do not treat canvas-local state as persistence.

Canvas responsibilities:
- render page image;
- pan/zoom;
- render entity boxes/polygons/labels;
- render connection geometry when available;
- selection/highlight;
- edit geometry only when explicitly enabled.

Canvas must not own engineering semantics.

## 3. Backend

Recommended stack:
- Python FastAPI.
- Pydantic models for API/domain validation.
- PostgreSQL for persistent domain state.
- Local filesystem storage for uploaded/rendered images in development.
- Object-storage adapter later.

Why Python:
- pyDEXPI integration is Python-based.
- graph analysis fits naturally with NetworkX or equivalent.
- PDF/image processing and AI-provider SDKs are straightforward.

Do not add Celery/Redis in v0.1 unless a real workload requires it. Start with an explicit job record + background execution/polling boundary that can be replaced later.

## 4. Document normalization

All supported inputs are normalized into page images.

```text
PNG/JPG ---------------------+
                             |
single-page PDF -> render ---+--> DocumentPage image
```

This gives the Canvas and AI pipeline one coordinate system.

Geometry should be persisted using normalized coordinates in [0, 1], relative to the rendered page dimensions. Pixel coordinates are derived at runtime.

## 5. Domain boundary

The central service owns `EngineeringGraph`.

```text
DigitizerProvider
       |
       v
Candidate EngineeringGraph
       |
       v
Validation + Review
       |
       +----------> Canvas / Inspector
       |
       +----------> GraphQueryService
       |
       +----------> DexpiAdapter
```

Do not let the VLM return arbitrary structures directly into UI state.

## 6. Digitizer provider interface

The first implementation may use one multimodal model, but code must depend on an interface, not a vendor.

Conceptual interface:

```python
class DigitizerProvider(Protocol):
    async def digitize(self, page: PageInput) -> DigitizationResult:
        ...
```

`DigitizationResult` must include:
- entities;
- connections;
- source evidence;
- confidence;
- warnings;
- provider metadata.

A provider may internally perform OCR, symbol recognition or multiple model calls. That complexity must not leak into the domain model.

The provider boundary accepts a normalized page-image input, instructions, task prompt, requested
JSON Schema, and optional provider settings. It returns validated proposal data plus normalized
provider/model, request ID, latency, usage, warning, and safe debug metadata. Provider output remains
a proposal and cannot mutate EngineeringGraph until a later validation/adapter stage. T009 supplies
only a deterministic fixture-driven mock; no real vendor is selected. `AI_PROVIDER`, `AI_MODEL`, and
`AI_API_KEY` are optional until AI functionality is invoked.

T010 adds an OpenAI adapter using the Responses API with image input and Pydantic structured-output
parsing. It is selected only with `AI_PROVIDER=openai`; `AI_MODEL` remains explicit configuration.
Validated entity candidates remain proposals and are not written to EngineeringGraph.

T011 exposes a synchronous, proposal-only `POST /documents/{id}/digitize` development path. It
runs entity extraction followed by topology extraction against the normalized page image. Topology
may reference only returned entity candidate IDs, all proposed relationships remain inferred, and
neither pass writes to the canonical EngineeringGraph. Durable job execution remains a later concern.

## 7. Two-stage extraction strategy

Prefer two logical stages:

### Stage A — entities
Identify:
- equipment;
- valves;
- instruments;
- boundary nodes;
- text/tag candidates.

### Stage B — topology
Infer or detect:
- process connections;
- utility connections;
- instrument ownership/association;
- connection evidence.

This separation makes evaluation and correction easier than one monolithic prompt.

## 8. Graph query before LLM

Topology questions must be answered in two layers:

```text
User question
   |
   v
Intent / entity resolution
   |
   v
Deterministic graph query
   |
   v
Structured answer + supporting IDs
   |
   v
Optional LLM verbalization
```

The LLM must not invent an upstream/downstream relationship that the graph query did not return.

## 9. DEXPI boundary

`EngineeringGraph` is canonical. `DexpiAdapter` is an output/integration boundary.

```python
class DexpiAdapter(Protocol):
    def validate_mappable(self, graph: EngineeringGraph) -> DexpiMappingReport:
        ...

    def map_supported(self, graph: EngineeringGraph) -> object:
        ...
```

For v0.1:
- support a narrow subset;
- produce explicit unmapped-field warnings;
- never silently drop missing engineering fields;
- keep DEXPI integration behind a feature flag.

Current pyDEXPI publicly supports DEXPI 1.3, while the current DEXPI specification family includes DEXPI 2.0 / P&ID 1.4. Therefore the adapter must be version-isolated.

pyDEXPI is AGPL-3.0. If this application is proprietary/closed-source, licensing must be resolved before shipping pyDEXPI as a product dependency. The internal schema must remain usable without pyDEXPI.

## 10. Persistence

Recommended v0.1 tables:

```text
documents
document_pages
graph_entities
graph_connections
graph_revisions
digitization_jobs
chat_threads
chat_messages
```

Large source files/page renders stay outside PostgreSQL; store paths/URIs in the database.

Use JSONB for flexible entity properties, but keep frequently queried identity/topology fields relational.

`EngineeringGraph` records are persisted in `graph_entities` and `graph_connections`; edits create
field-level rows in `graph_revisions`. `GET /documents/{id}/graph` reconstructs the canonical aggregate
from those records. New documents have an empty graph by default. The development-only
`DEMO_MOCK_GRAPH` flag may idempotently seed the explicit T004 fixture after upload; it defaults to
`false` and must not be treated as normal product digitization.

The web application identifies a reopened document with the `documentId` URL query parameter and
reloads both the document/page and its canonical graph from the API.

## 11. Revision model

Every user edit should be attributable.

Minimum approach:
- graph entity/connection has `updated_at`;
- every edit creates a lightweight revision event;
- revision stores actor, object ID, field, before, after, timestamp.

Full collaborative CRDT/event-sourcing is out of scope.

## 12. API shape

Suggested v0.1 endpoints:

```text
POST   /documents
POST   /documents/{id}/upload
GET    /documents/{id}
GET    /documents/{id}/graph

POST   /documents/{id}/digitize
GET    /digitization-jobs/{id}

PATCH  /entities/{id}
POST   /documents/{id}/connections
PATCH  /connections/{id}
DELETE /connections/{id}

POST   /documents/{id}/graph/query
POST   /documents/{id}/chat

POST   /documents/{id}/dexpi/validate
POST   /documents/{id}/dexpi/export
```

DEXPI export may initially return "not enabled" unless the licensing/version gate is cleared.

## 13. Testing strategy

Tests are layered:

1. Domain tests — graph validation, IDs, connection integrity.
2. API tests — CRUD/edit persistence.
3. Frontend tests — selection/inspector edit.
4. Benchmark tests — compare digitizer output with hydrolysis reference registers.
5. Regression snapshots — fixed provider response -> fixed graph result.

Do not make live paid-model calls in the normal unit-test suite.

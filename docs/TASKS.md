# TASKS.md — P&ID Digitizer v0.1

## Working rule

Implement one vertical slice at a time.
Each task must leave the repo runnable.
Do not implement future tasks "while you're here".

## Phase 0 — Repository

### T000 — Scaffold monorepo
Create:
- `apps/web`: Next.js + TypeScript.
- `services/api`: FastAPI + Pydantic.
- local PostgreSQL in Docker Compose.
- root scripts for dev/test/lint.
- `.env.example`.

Acceptance:
- one command starts web + API + DB;
- web can call `/health`;
- CI-style lint/test commands pass.

### T001 — Domain model first
Implement EngineeringGraph Pydantic models and TypeScript mirror types from DATA_MODEL.md.

Acceptance:
- invalid missing connection references are detected;
- geometry/confidence validation works;
- JSON round trip works;
- unit tests pass.

## Phase 1 — Real UI, fake AI

### T002 — Upload and render
Upload PNG/JPG or single-page PDF.
Backend normalizes PDF to a page image.

Acceptance:
- created Document + DocumentPage persist;
- web shows page image;
- unsupported/multi-page input gets a clear v0.1 error.

### T003 — Canvas
Use react-konva.

Acceptance:
- pan;
- zoom centered around cursor;
- fit-to-screen;
- base image remains sharp enough for inspection.

### T004 — Mock graph overlay
Load a fixed EngineeringGraph fixture.

Acceptance:
- entity boxes/labels render;
- selection/highlight works;
- layer toggles for entities/connections.

### T005 — Inspector edit loop
Inspector edits `kind`, `subtype`, `tag`, `displayName`, properties and review status.

Acceptance:
- save PATCHes backend;
- canvas updates without reload;
- refresh preserves edit;
- revision event is created.

### T006 — Connection editor
Inspect/add/edit/delete a connection.

Acceptance:
- entity selector resolves source/target;
- invalid missing IDs rejected;
- connection appears in graph immediately.

## Phase 2 — Benchmark

### T007 — Hydrolysis benchmark adapter
Build an adapter for the existing hydrolysis workbook/pre-DEXPI structure.

Acceptance:
- imports equipment nodes;
- imports process connections;
- imports instrument register;
- preserves confidence/source/status;
- validator reports broken references.

### T008 — Benchmark UI fixture
Choose one hydrolysis DCS screen as the v0.1 benchmark page.

Acceptance:
- expected objects can be loaded from reference data;
- unsupported geometry is explicitly marked missing rather than fabricated.

## Phase 3 — Real digitization

### T009 — DigitizerProvider interface
Create vendor-neutral provider interface + fake provider.

Acceptance:
- fake provider drives the exact same ingestion path as a real provider;
- provider metadata is stored.

### T010 — First multimodal entity extraction
Implement one real model provider.

Scope:
- equipment;
- valves;
- instruments;
- boundary nodes;
- text/tag candidates.

Acceptance:
- output is schema-validated;
- every candidate includes provenance/confidence when available;
- malformed provider response cannot corrupt persisted graph.

### T011 — Topology extraction
Second logical pass for connections/ownership.

Acceptance:
- source/target IDs must resolve;
- inferred connections are marked `assertion.mode = inferred`;
- warnings retained for ambiguous links.

### T012 — Evaluation script
Compare prediction against benchmark registers.

Metrics:
- entity matching;
- tag exact match;
- connection matching;
- instrument-owner match;
- graph integrity errors.

Acceptance:
- outputs machine-readable JSON + concise console report;
- no live model call required when evaluating saved prediction fixtures.

## Phase 4 — Query and chat

### T013 — Deterministic graph query API
Implement:
- neighbors;
- upstream;
- downstream;
- shortest path;
- entity lookup by ID/tag.

Acceptance:
- returns structured IDs + paths;
- no LLM is required.

### T014 — Chat orchestration
Resolve user intent/entity -> call graph query -> optional LLM verbalization.

Acceptance:
- final response includes supporting entity/connection IDs;
- if graph has no answer, assistant says the graph does not establish it;
- chat can request canvas highlight by returned IDs.

## Phase 5 — DEXPI boundary

### T015 — DexpiAdapter interface
Implement validation/reporting without requiring pyDEXPI.

Acceptance:
- supported/unmapped/blocked fields are explicit;
- no silent data loss.

### T016 — pyDEXPI spike behind feature flag
Only after license/version decision.

Acceptance:
- isolated dependency;
- maps a tiny reviewed subset;
- failure cannot mutate canonical EngineeringGraph;
- documented compatibility and licensing decision.

## Phase 6 — v0.1 hardening

### T017 — UX polish
- loading/error/empty states;
- keyboard delete/escape;
- undo for last local edit where practical;
- confidence/review visual treatment.

### T018 — End-to-end test
One hydrolysis benchmark screen:
upload -> graph -> edit -> persistence -> topology query -> highlight.

### T019 — v0.1 demo checklist
Prepare a deterministic demo project and saved model output so the demo does not depend on a live AI call.

## Not before v0.1

Do not start:
- multi-page PDFs;
- custom vision-model training;
- full PFD/HMI generalization;
- collaboration;
- full DEXPI 2.0 exporter;
- safety/interlock reasoning;
- production control integration.

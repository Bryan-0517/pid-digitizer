# PRODUCT.md — P&ID Digitizer v0.1

## 1. Product goal

Build an independent web application that turns engineering diagrams into an editable, machine-readable engineering graph.

The long-term product vision is:

**engineering drawing → structured engineering graph → human review/editing → DEXPI mapping → grounded engineering Q&A**

The v0.1 goal is deliberately narrower. It must prove one complete end-to-end workflow with good architecture, not broad format coverage.

## 2. v0.1 user story

A user can:

1. Create/open a document.
2. Upload a PNG/JPG image or a single-page PDF.
3. View the rendered diagram on an interactive canvas.
4. See detected engineering objects and connections as overlays.
5. Click an object to inspect its type, tag, properties, confidence, provenance and review status.
6. Edit an object or connection.
7. Save the corrected model.
8. Ask deterministic topology questions such as:
   - What is upstream/downstream of X?
   - What is connected to X?
   - What path connects A to B?
9. Optionally receive an LLM-written answer that is grounded in the graph-query result.
10. Map supported, reviewed objects into a DEXPI adapter without making pyDEXPI the application's source of truth.

## 3. v0.1 supported input

### In scope
- PNG/JPG engineering diagrams.
- Single-page PDF, rendered by the backend to a raster page before annotation.
- Clear P&ID-like drawings.
- The existing hydrolysis DCS/HMI screenshots as the first workflow benchmark.

### Explicitly out of scope for v0.1
- Multi-page document management.
- Full PFD + P&ID + HMI + PIC coverage.
- Production-grade OCR across every drawing style.
- Automatic recognition of every ISA/DEXPI symbol.
- Full control-loop reconstruction.
- Safety-critical conclusions.
- Automatic plant-control actions.
- Full DEXPI 2.0 export.
- Multi-user simultaneous editing.
- Training a custom vision model.

## 4. The core product rule

**EngineeringGraph is the source of truth.**

The Canvas is a view/editor of EngineeringGraph.
The AI digitizer produces candidate EngineeringGraph data.
Chat queries EngineeringGraph.
The DEXPI adapter maps EngineeringGraph into a DEXPI representation.

Do not store independent copies of the same engineering meaning in Canvas state, chat state and DEXPI state.

## 5. Human-in-the-loop is a first-class feature

AI output is not assumed to be correct.

Every machine-produced object/connection should carry:
- confidence;
- provenance/evidence;
- observed vs inferred status;
- review status.

The UI must make it easy to correct the graph.

## 6. Hydrolysis benchmark

The first benchmark is the existing hydrolysis DCS/pre-DEXPI package. It contains 9 DCS screens, 10 process areas and 156 equipment/boundary nodes in the current workbook. It also contains process connections, instrument candidates, AI variables, operation stages, control points and DEXPI-gap tracking.

Important: this package is **not** a certified P&ID and **not** final DEXPI. It should be used to test extraction/editing/topology workflows, not formal DEXPI conformance.

The benchmark should measure at least:
- entity recall/precision where comparable;
- tag exact-match accuracy;
- connection precision/recall where comparable;
- instrument-owner accuracy;
- number of human edits required;
- broken-reference count after ingestion.

## 7. v0.1 success criteria

v0.1 is successful when all of the following work on at least one hydrolysis screen:

- Upload/render works.
- Pan and zoom work smoothly.
- Mock or real detected entities render as overlays.
- Clicking an entity opens the inspector.
- Editing tag/type/properties updates EngineeringGraph and the canvas immediately.
- Connections can be inspected and edited.
- Reloading the document preserves edits.
- A graph query can return upstream/downstream/path results without using an LLM.
- Chat can explain a graph-query result and identify the supporting entity IDs.
- A DEXPI adapter can accept supported reviewed entities behind a feature flag.
- Automated tests cover graph validation and the main edit flow.

## 8. Product principles

1. Correctable beats impressive.
2. Evidence must survive the AI pipeline.
3. Deterministic graph queries come before LLM answers.
4. Internal schema must not be coupled to one model vendor.
5. Internal schema must not be coupled to one DEXPI library/version.
6. Do not infer safety-critical engineering facts that are not present in source evidence.

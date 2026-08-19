# P&ID Digitizer

An AI-assisted web application for converting engineering diagrams into structured, reviewable engineering data.

P&ID Digitizer is designed to help transform information contained in engineering drawings into a persistent **EngineeringGraph**, while keeping engineers in control of validation and correction.

> **v0.1 Proof of Concept**
> The current version focuses on entity extraction, human-in-the-loop review, graph persistence, and deterministic topology queries.

<!-- Add application screenshot here later -->

---

## Overview

Engineering drawings often contain valuable information about equipment, instruments, tags, and connections, but much of this information remains locked inside images or PDF documents.

P&ID Digitizer provides a workflow to:

1. Import an engineering diagram.
2. Generate candidate engineering entities from the source document.
3. Review and correct extracted information.
4. Persist approved information in a structured EngineeringGraph.
5. Query engineering relationships using the structured graph.
6. Maintain provenance between structured data and the original source evidence.

The goal is not to treat AI output as ground truth. AI-generated information is handled as a **proposal** that can be reviewed and corrected before becoming trusted engineering data.

---

## Key Features

### Interactive Engineering Diagram Viewer

View engineering drawings in an interactive browser-based canvas with support for navigation and entity overlays.

### AI-Assisted Entity Proposals

Extract candidate engineering entities from source diagrams while retaining information such as provenance and review state.

### Human-in-the-Loop Review

Engineers can inspect, modify, and validate proposed information before it becomes part of the canonical engineering dataset.

### Persistent EngineeringGraph

Reviewed entities and relationships are stored as structured engineering data rather than remaining only as annotations on an image.

### Graph-Based Engineering Queries

Topology questions can be answered from the structured EngineeringGraph instead of relying on an LLM to infer connectivity directly from an image.

Example:

```text
What is connected to TV_0806B?
```

The system identifies canonical connected entities and provides supporting entity and connection information.

### DEXPI-Oriented Data Model

The project explores structured engineering data representation and DEXPI-oriented interoperability while keeping the internal EngineeringGraph as the canonical application model.

---

## Architecture

The application follows a web-based architecture:

```text
Engineering Diagram
        ↓
     Web App
        ↓
   Backend API
        ↓
EngineeringGraph
        ↓
   PostgreSQL
```

The project separates:

* source documents,
* AI-generated proposals,
* reviewed canonical engineering data,
* provenance,
* and graph relationships.

This separation prevents model-generated output from automatically becoming trusted engineering truth.

More detailed technical documentation is available in:

* `docs/PRODUCT.md`
* `docs/ARCHITECTURE.md`
* `docs/DATA_MODEL.md`

---

## Repository Structure

```text
pid-digitizer/
├── apps/               # Web application
├── services/           # Backend services
├── schemas/            # Shared data schemas
├── benchmarks/         # Development and benchmark materials
├── demo/               # Deterministic demo resources
├── docs/               # Product and technical documentation
├── docker-compose.yml
└── README.md
```

---

## Demo

A deterministic v0.1 demonstration is included in the repository.

The demo uses a **previously saved entity-proposal snapshot** rather than making a live AI request. This keeps the demonstration reproducible and avoids presenting model-generated benchmark data as certified engineering truth.

The demo includes:

* an engineering diagram viewer,
* proposal-derived engineering entities,
* human review and correction,
* persistent canonical data,
* a reviewed engineering connection,
* and deterministic Graph Chat topology queries.

Detailed setup and presenter instructions are available in:

[`docs/DEMO.md`](docs/DEMO.md)

### Demo Video

Demo video: **Coming soon**

---

## Running the Deterministic Demo

Follow the complete setup instructions in `docs/DEMO.md`.

The demo workflow includes commands for starting, preparing, checking, resetting, and cleaning up the local environment.

The final demonstration is designed to run locally and does not require a live AI provider.

---

## Browser End-to-End Testing

The repository includes a Playwright browser end-to-end test.

Install Chromium once:

```bash
npx playwright install chromium
```

Then run:

```bash
npm run test:e2e
```

The test environment uses a disposable Docker Compose project with isolated PostgreSQL and document-storage volumes.

The browser uploads the development input:

```text
benchmarks/hydrolysis/images/IMG_6807.JPG
```

Upload creates the normal persisted document and page records but does **not** automatically create canonical engineering content.

A test-only helper seeds a minimal explicitly labelled fixture consisting of two entities and one connection so that the browser workflow can test application mechanics.

This fixture is intended for software testing only and must not be interpreted as production or benchmark engineering ground truth.

---

## Benchmark Materials

`benchmarks/hydrolysis/reference/` contains the currently available hydrolysis pre-DEXPI reference materials.

Development images are stored under:

```text
benchmarks/hydrolysis/images/
```

The hydrolysis package is used as a **workflow and topology benchmark**.

It is not certified P&ID or DEXPI ground truth.

Any benchmark or engineering material must be reviewed for distribution and privacy requirements before being included in a public repository.

---

## Design Principle

A central principle of the project is:

```text
AI output ≠ engineering ground truth
```

Model-generated information remains a proposal until it has gone through the appropriate review process.

The canonical EngineeringGraph remains separate from raw model output and retains provenance back to the original source material.

---

## Current Status

P&ID Digitizer is currently a **v0.1 proof of concept**.

The current implementation demonstrates the core workflow:

```text
Engineering Diagram
        ↓
Entity Proposals
        ↓
Human Review
        ↓
Canonical EngineeringGraph
        ↓
Deterministic Engineering Queries
```

Future work may include broader document support, richer topology extraction, improved engineering-object recognition, and expanded interoperability with engineering data standards.

---

## Development Documentation

Additional internal development documentation is available in the `docs/` directory.

For development workflow and task history, see:

* `docs/TASKS.md`
* `AGENTS.md`
* `CLAUDE.md`

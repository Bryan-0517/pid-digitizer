# AGENTS.md

## Mission

Build P&ID Digitizer v0.1 according to the documents in `/docs`.

## Non-negotiable architecture rules

1. `EngineeringGraph` is the canonical engineering state.
2. Canvas state is presentation/interaction state, not a second engineering database.
3. AI providers must implement a provider interface.
4. Graph topology questions must have a deterministic query implementation before LLM verbalization.
5. DEXPI is an adapter boundary, not the canonical state.
6. Never fabricate geometry, tags, connections or engineering properties to make a demo look complete.
7. Preserve confidence, provenance, observed/inferred status and review state.
8. Do not add Redis, Celery, Kubernetes, vector DBs or microservices without an active task requiring them.
9. Do not expand v0.1 scope.
10. Add tests with each task.

## Task protocol

Before coding:
- read PRODUCT.md, ARCHITECTURE.md, DATA_MODEL.md and the current task;
- state the files you expect to change;
- identify any conflict with the docs.

After coding:
- run tests/lint;
- summarize changed files;
- report compromises/TODOs;
- do not begin the next task automatically.

## Safety

This product must not present inferred DCS/P&ID information as verified engineering truth.
Do not implement automated plant-control actions.

# P&ID Digitizer Bootstrap

This repository is the v0.1 design/bootstrap package for an independent P&ID Digitizer web app.

## Start here

Read in this order:

1. `docs/PRODUCT.md`
2. `docs/ARCHITECTURE.md`
3. `docs/DATA_MODEL.md`
4. `docs/TASKS.md`
5. `AGENTS.md`

Then give the coding agent **T000 only**.

Do not ask Claude Code/Codex to "build the whole app".

## Benchmark

`benchmarks/hydrolysis/reference/` contains the currently available hydrolysis pre-DEXPI reference materials.

The raw DCS screenshots should be copied into:

`benchmarks/hydrolysis/images/`

The hydrolysis package is a workflow/topology benchmark, not certified P&ID/DEXPI ground truth.

## T018 browser end-to-end test

Run `npx playwright install chromium` once, then `npm run test:e2e`. The Playwright setup starts a
Docker Compose project named `pid-digitizer-t018` with a disposable PostgreSQL volume and document
storage volume, binds the API/web only to localhost ports 18000/13000, and removes those volumes
after the run.

The browser uploads the real DEV input `benchmarks/hydrolysis/images/IMG_6807.JPG`. Upload creates
only the normal persisted Document and DocumentPage; it does **not** accept digitization proposals
or create canonical engineering content. A helper mounted only in the E2E API container then seeds
two explicitly test-labelled entities and one connection for the actual uploaded document/page.
That minimal fixture tests application mechanics and is neither production canonical truth nor
benchmark semantic truth. AI configuration, the demo graph, pyDEXPI, and DEXPI export are disabled.

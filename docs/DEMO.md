# P&ID Digitizer v0.1 deterministic local demo

## Purpose and boundary

This local-only demo exercises the existing persisted-document, canonical editing, deterministic
topology-query, and canvas-highlight workflow without a live AI call. It is not a deployment
package, proposal-acceptance feature, verified plant model, P&ID certification, or DEXPI conformance
demonstration. Future distribution of the hydrolysis materials requires a separate privacy and
distribution decision.

The architecture remains: Next.js browser UI -> FastAPI -> PostgreSQL canonical `EngineeringGraph`.
The canvas and Graph Chat highlights are presentation state. T013 answers topology deterministically;
T014 only orchestrates that query and uses `verbalize:false`.

## Fixed inputs and provenance

- DEV source: `benchmarks/hydrolysis/images/IMG_6807.JPG`
- Saved output: `benchmarks/hydrolysis/evaluations/fixtures/IMG_6807.openai-gpt5.tiled-20260816-02-validation-v1.proposal.json`
- Required saved label: **MODEL OUTPUT SNAPSHOT — NOT BENCHMARK TRUTH**
- Provider metadata already captured in the artifact: OpenAI, `gpt-5-2025-08-07`
- The snapshot has 131 entity candidates and **zero topology proposals**.
- Manifest: `demo/t019-manifest.json`

The prepared canonical state contains only two proposal-derived entities: instrument `FI_0828` from
candidate `instruments:r1c0:inst-3` and valve `FV_0827` from candidate
`valves:r1c0:valve-7`. Their exact stored candidate boxes were manually compared with IMG_6807:
the first encloses the `FI_0828` display and tag; the second encloses the `FV_0827` tag, red valve
symbol, and green branch. No geometry was adjusted or invented. Confidence is absent because the
proposal supplies none. Both begin `assertion=inferred`, `reviewStatus=unreviewed`, with
model-candidate provenance. This source-correspondence review does not make either entity verified
plant engineering truth.

For presentation only, the web app also reads that committed snapshot locally and displays eight
proposal-only boxes. They are not inserted into `EngineeringGraph`, persisted, queried, reviewed,
or sent to DEXPI. The presentation uses a fixed allowlist whose exact stored boxes were manually
compared with visible source evidence. It excludes the two canonical candidates and does not infer
correctness from box size, score, or page distribution. The selected snapshot candidate IDs are:

- `equipment_boundary:r0c0:cand-1`
- `equipment_boundary:r0c0:cand-6`
- `equipment_boundary:r0c0:cand-7`
- `equipment_boundary:r1c1:bdry-top-header`
- `equipment_boundary:r1c1:bdry-inlet-D`
- `equipment_boundary:r1c1:bdry-inlet-F`
- `equipment_boundary:r1c1:bdry-inlet-G`
- `equipment_boundary:r1c1:bdry-bottom-header`

These are unreviewed model-output visualizations, not benchmark truth or verified engineering truth.
Their muted dashed boxes sit behind the stronger solid canonical overlays and can be hidden with the
**AI proposals** checkbox. No live model call occurs.

The one connection was not produced by the model. A human directly reviewed IMG_6807 and confirmed
only a visible reference association between `FI_0828` and `FV_0827`: they occupy the same visible
feed-control column, and the continuous green branch below the FI display passes through the FV
valve symbol. It is stored as `human_added`/`confirmed`, `kind=reference`, no confidence, no
connection geometry, and `direction=unknown`. The endpoint ordering is structural only. This is not
a process-flow, upstream/downstream, or formal control-loop claim. Benchmark truth and evaluation
matches were not used.

## Prerequisites

- Docker Desktop with Compose
- Node.js 20+
- Local ports 14000 and 19000 available
- Repository dependencies installed with `npm install`

## Lifecycle commands

From the repository root:

```powershell
npm run demo:start
npm run demo:setup
npm run demo:check
```

Open:

`http://127.0.0.1:14000/?documentId=t019-demo-img6807`

Restore the exact initial state after edits:

```powershell
npm run demo:reset
npm run demo:check
```

Stop services and delete only the isolated demo volumes:

```powershell
npm run demo:cleanup
```

`demo:setup` and `demo:reset` are idempotent. They refuse to act unless the database name is exactly
`pid_digitizer_demo`, all AI configuration is empty, mock seeding is disabled, and pyDEXPI export is
disabled.

## Feature flags

| Setting | Demo value |
|---|---|
| `DEMO_MOCK_GRAPH` | `false` |
| `AI_PROVIDER` | empty |
| `AI_MODEL` | empty |
| `AI_API_KEY` | empty |
| `INSTALL_PYDEXPI` | `false` |
| `PYDEXPI_EXPORT_ENABLED` | `false` |
| API URL | `http://127.0.0.1:19000` |
| Web URL | `http://127.0.0.1:14000` |

No digitization endpoint is invoked during setup or presentation.

## Presenter checklist

1. Run `npm run demo:check`; expect JSON with `status=ready`, entity IDs `t019:entity:fi-0828` and
   `t019:entity:fv-0827`, connection ID `t019:connection:fi-0828--fv-0827`,
   `topologyProposalCount=0`, and `aiProviderInvoked=false`.
2. Open the exact URL above; expect `IMG_6807.JPG`, two strong canonical overlays, and eight visible,
   dashed proposal-only overlays. Toggle **AI proposals** to demonstrate the separate visual layer.
3. Explain the source image, fixed entity-only saved snapshot, prepared editable canonical state, and
   separately human-reviewed connection. State that no live AI call occurred.
4. Briefly drag, zoom, and select **Fit to screen**.
5. Select the `FI_0828` instrument overlay; expect confidence **Not provided**, assertion
   **inferred**, review status **unreviewed**, and provenance referencing candidate
   `instruments:r1c0:inst-3`. Select `FV_0827` and verify provenance references
   `valves:r1c0:valve-7` and the solid canonical overlay remains visually dominant.
6. Human review action: change Display name from `FI 0828` to `Reviewed flow indicator` and
   Review status to `corrected`; select **Save**.
7. Reload the same URL, select `FI_0828`, and expect the display name and `corrected` state to persist.
   Assertion remains `inferred`; the existing PATCH API does not rewrite origin history.
8. Ask exactly: **What is connected to FI_0828?**
9. Expect: **FI_0828 has 1 directly connected canonical entities.**
10. Expect supporting entities `t019:entity:fi-0828, t019:entity:fv-0827` and supporting connection
    `t019:connection:fi-0828--fv-0827`.
11. Expect both entity IDs to have high-contrast canvas highlights while Inspector selection remains
    the single `t019:entity:fi-0828`. The **Highlighted topology** notice shows
    `FI_0828 ↔ FV_0827` and **Connection geometry not recorded.**
    No connection line is drawn because the canonical relationship has no geometry. Query and
    highlight behavior are read-only. Do not demonstrate an upstream/downstream query.
12. Run `npm run demo:reset` and `npm run demo:check`. Reopen the URL; expect blank Display name,
    inferred/unreviewed entities, the confirmed human-added connection, and no revision history.

## Optional T015 appendix

DEXPI preflight may be run from the existing panel after reset. It is dependency-free and read-only.
Its supported/unmapped/blocked dispositions and warnings must be shown verbatim. It is not DEXPI
conformance, export certification, or evidence that inferred/unreviewed entities are verified.

T016 is deliberately absent: pyDEXPI is not installed, compatibility export is disabled, its AGPL-3.0
distribution implications remain unresolved, and the spike is not a standard DEXPI exchange path.

## Readiness and troubleshooting

- `npm run demo:check` validates asset hashes, proposal identity/counts, manifest-to-candidate fields,
  canonical graph integrity, provenance separation, initial review states, revision count, T013
  neighbors, and the exact provider-free T014 response. The web proposal endpoint is a separate
  non-canonical visualization check and does not change the expected graph counts.
- If ports 14000/19000 are occupied, stop the conflicting local service; do not point the demo at a
  developer database.
- If setup reports an asset hash mismatch, restore the committed fixed artifact rather than editing it.
- If state differs after presenting, run `npm run demo:reset`.
- Diagnostic output stays local. Do not upload the image, traces, screenshots, or saved artifacts.

## Known v0.1 limitations

- There is no production proposal-acceptance/import workflow.
- Only two saved entity candidates and one independently human-reviewed connection are prepared as
  canonical state; the eight additional boxes are proposal-only visualizations.
- Proposal geometry is model output, not benchmark truth. The fixed presentation allowlist was
  manually checked only for visible source correspondence and remains non-canonical/unreviewed.
- A visible `FI_0828`/`FV_0827` reference association is confirmed; connection geometry and direction
  are deliberately absent, and no process-flow or formal control-loop semantics are claimed.
- Graph Chat supports only the documented deterministic intent patterns.
- Multi-page documents, collaboration, safety reasoning, and automated plant control remain out of scope.

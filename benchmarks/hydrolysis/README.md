# Hydrolysis EngineeringGraph adapter

This deterministic adapter reads the hydrolysis pre-DEXPI workbook and produces the canonical
EngineeringGraph fixture in `expected/`. The source is engineering reference material, not a
certified P&ID or DEXPI model.

## Fixture identities

- `documentId` is `benchmark:hydrolysis`.
- Every T007 entity uses `pageId` `benchmark:hydrolysis:unassigned`. This is only a mandatory-field
  sentinel and is not evidence of association with one particular screen. T008 may replace it with
  a real benchmark DocumentPage ID where reliable.
- Missing source timestamps use `1970-01-01T00:00:00Z`. This makes output deterministic and makes no
  historical claim.
- All actual `IMG_*.JPG` source references are retained as separate provenance entries.

## Mapping rules

- `equipment_nodes` become equipment entities, except source IDs beginning `BND_`, which become
  boundaries. Source equipment type becomes subtype; other source fields remain properties.
- `instrument_register` becomes instrument entities. A valid owner creates exactly one ownership
  edge from instrument to owner with `direction=source_to_target`. Missing, broken, or ambiguous
  owners create no edge and are reported.
- `process_connections` types `Process` and `Utility` map to `process` and `utility`; all other values
  map to `unknown`. No geometry is generated.
- Source status `已确认` maps to `confirmed`; `待现场核实`, `待补资料`, and `待确认` map to
  `needs_source`; other statuses remain `unreviewed`.
- Evidence whose extraction basis mentions AI, a flow/process basis, or inference maps to
  `assertion.mode=inferred`; otherwise it maps to `observed`. Review status remains independent and
  uncertain rows never become confirmed.
- Source confidence is copied exactly. Missing confidence remains absent.
- Canonical IDs use register-specific deterministic namespaces. Conflicting duplicate source node
  IDs are preserved as separate area/occurrence-qualified entities; references to those ambiguous
  IDs are reported and not guessed.

Run from the repository root with the API package available:

```powershell
$env:PYTHONPATH='services/api'
python benchmarks/hydrolysis/convert.py
```

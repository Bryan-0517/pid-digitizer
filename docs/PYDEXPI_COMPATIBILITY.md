# pyDEXPI compatibility spike (T016)

T016 is a development-only, version-specific compatibility spike. It proves a narrow path from the canonical `EngineeringGraph`, through the dependency-free T015 preflight, into real pyDEXPI objects and pyDEXPI JSON serialization. `EngineeringGraph` remains the sole canonical engineering state.

## Fixed compatibility target

- Python runtime: 3.12 or newer
- package: `pydexpi==1.2.0`
- target model version: DEXPI 1.3
- artifact label: **pyDEXPI 1.2.0 / DEXPI 1.3 compatibility JSON**

The artifact wraps pyDEXPI's public JSON representation with a deterministic conversion report. It is not claimed to be the standard DEXPI industry exchange format, a conformant exchange file, or conformance certification. Proteus XML and pickle export are not implemented.

## Availability and dependency isolation

`PYDEXPI_EXPORT_ENABLED` defaults to `false`. The optional dependency is installed in an API image only when build argument `INSTALL_PYDEXPI=true` is supplied. With the feature disabled, API startup and T015 validation do not import or require pyDEXPI. Enabling the feature without exactly version 1.2.0 installed reports export as unavailable.

## Exact tiny mapping

Only confirmed/corrected, non-inferred T015-eligible canonical equipment with an unambiguous explicit hint is constructed:

- `equipment` subtype `centrifugal_pump`, or allowlisted advisory `dexpi.suggestedClass=CentrifugalPump`, maps to public pyDEXPI `CentrifugalPump`.
- `equipment` subtype `tank`, or allowlisted advisory `dexpi.suggestedClass=Tank`, maps to public pyDEXPI `Tank`.

Only canonical `id`, `kind`, and `tag` are counted as converted fields. Suggested classes are advisory allowlisted hints, never dynamically resolved class names, and are not mutated. Generic equipment, instruments, connections, and geometry are not converted. No topology or geometry is fabricated.

T015 policy is enforced as follows:

- A blocked object blocks the entire document export and its IDs/reason codes are returned.
- An unmapped object is preserved canonically, omitted from construction, and listed explicitly.
- A partial object may be included only when the exact mapping and required fields are eligible; every other field is reported as omitted.
- An empty graph returns a deterministic no-content outcome.

Export is transient and download-only. It creates no export record, revision, blob, mapping-status update, review change, assertion change, or parallel DEXPI state.

## Licensing boundary

pyDEXPI is AGPL-3.0. T016 is an isolated development compatibility spike and is not production/proprietary deployment licensing approval. Production inclusion or distribution requires separate project/legal approval; commercial/custom licensing may be required depending on deployment.

Conversion/export coverage beyond this spike remains incomplete and belongs to later explicitly approved work.

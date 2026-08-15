# IMG_6807 semantic evaluation

`evaluate.py` compares a validated entity proposal with the T008 page-scoped semantic reference.
Reference data is loaded only after extraction. Matching is one-to-one and uses, in order: exact
conservatively normalized tag, exact source/DCS identifier, then exact conservatively normalized
display name. Ambiguous matches remain unscored.

Tag normalization trims outer whitespace, folds case, and removes whitespace immediately around
existing `_` or `-` separators. It does not interchange separators, repair characters, or perform
engineering reinterpretation.

Semantic precision is matched candidates divided by all proposed candidates; semantic recall is
matched references divided by all 64 page-scoped reference entities; F1 is their harmonic mean.
Exact-tag accuracy uses matched pairs where both sides have tags. Kind accuracy uses all matched
pairs. Instrument precision divides correct instrument-to-instrument matches by proposed
instruments; instrument recall divides them by the 43 reference instruments. Every ratio records
its numerator and denominator in the artifact, including zero-denominator cases.

The benchmark has no verified bbox, polygon, or polyline geometry. Output therefore labels bbox
counts as **geometry proposal coverage/validity**, never geometry accuracy. It does not calculate
IoU, localization accuracy, or connection-path accuracy. Malformed/out-of-range proposal geometry
is rejected by the validated proposal schema before evaluation; the diagnostic counts degenerate
zero-area boxes that remain structurally valid.

The committed `no-model-baseline` proposal and evaluation are deterministic plumbing fixtures, not
AI predictions or benchmark truth. A real validated `POST /documents/{id}/digitize` response can be
evaluated offline without another paid model request:

```powershell
$env:PYTHONPATH='services/api'
python benchmarks/hydrolysis/evaluate.py `
  path/to/validated-digitization-response.json `
  benchmarks/hydrolysis/evaluations/IMG_6807.<run-id>.evaluation.json `
  --run-id <run-id>
```

Artifacts may contain validated proposals and safe provider usage metadata, but must never contain
API keys or raw vendor response payloads.

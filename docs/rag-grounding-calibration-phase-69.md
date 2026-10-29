# Phase 69 — Automated grounding calibration release decisions

Phase 69 adds a deterministic release-gate policy and CLI on top of Phase 68's
explicitly approved baseline manifests. It does not approve or update baselines
automatically. The gate fails closed when the manifest/report cannot be read,
the manifest integrity check fails, or report validation fails.

## Run a release decision

Generate the candidate report and compare it to a reviewed manifest:

```bash
python -m services.rag.grounding_calibration_cli \
  --output calibration-current.json

python -m services.rag.calibration_release_gate_cli \
  --baseline-manifest tests/fixtures/rag/grounding-calibration-baseline.json \
  --current calibration-current.json \
  --output artifacts/rag-calibration-release-decision.json
```

Exit codes are stable: `0` means policy passed, `1` means a valid comparison
found regressions, and `2` means invalid inputs or an artifact-write failure.
The JSON decision is written atomically for both pass and regression outcomes;
invalid inputs also produce an error decision when the output path is writable.
CI systems should archive the decision JSON even when the gate fails.

## Policy controls

All metric-drop tolerances default to zero and must be finite values from zero
through one:

- `--max-accuracy-drop`
- `--max-macro-f1-drop`
- `--max-class-f1-drop`
- `--max-group-accuracy-drop`

Newly failing shared cases fail by default. The opt-out
`--allow-new-case-failures` should only be used when a reviewed policy
explicitly permits that behavior. The decision artifact includes the baseline
version and hashes, current report hash, thresholds, comparison deltas, and
ordered regression messages so a release decision can be audited and compared.

## CI and approval boundary

The repository's Python CI job runs the release-gate tests as part of the full
pytest suite. A deployment pipeline can invoke the CLI once a reviewed baseline
manifest has been explicitly committed or supplied as a protected artifact.
Do not create the baseline from the candidate report in the same job: that
would compare the candidate to itself and defeat regression detection.

A passing result establishes only that the supplied offline fixture report
satisfied the configured policy. It is not proof of semantic entailment,
factual correctness, or production safety. SHA-256 fingerprints detect content
changes but are not digital signatures or proof of reviewer identity.

# Phase 70 — Calibration corpus drift protection

Phase 70 strengthens Phase 69's release decision with an explicit case-set
policy. A calibration report can keep the same aggregate accuracy while
silently adding or removing fixture cases, so case-set changes are now release
regressions by default whenever both reports include per-case results.

## Default policy

The release gate now fails when the candidate has added or removed case IDs.
The JSON decision includes a stable `case_set_changes` object with sorted
`added` and `removed` arrays, even when the override is enabled. The
regression list contains a reason for each change. This is separate from the
existing rule that fails on newly failing shared cases.

Use the opt-out only when the change has been reviewed and intentionally
approved:

```bash
python -m services.rag.calibration_release_gate_cli \
  --baseline-manifest tests/fixtures/rag/grounding-calibration-baseline.json \
  --current grounding-calibration-current.json \
  --output artifacts/rag-calibration-release-decision.json \
  --allow-case-set-change
```

This option permits case additions/removals only; it does not disable metric
regression checks or the default newly-failing-case check. The decision artifact
records the selected policy so reviewers can distinguish a clean match from an
explicitly permitted corpus update.

## Approval and baseline activation

Do not auto-approve the current report as its own baseline. A production
baseline should be generated from a reviewed report, have a human approval
reason, be verified with `calibration_baseline_cli verify`, and be introduced
through a reviewed repository change. Once that manifest exists at
`tests/fixtures/rag/grounding-calibration-baseline.json`, the existing CI
workflow detects it and runs the release gate. Until then, CI continues to
generate and archive calibration reports without pretending an approval exists.

The corpus remains an offline lexical regression suite, not a semantic
entailment benchmark or a guarantee of factual correctness or production safety.

# Phase 66 — Per-status metrics and macro-F1 gate

Phase 66 extends the offline grounding calibration report with one-vs-rest
classification metrics for each supported status: `grounded`, `unsupported`,
`contradictory`, and `inconclusive`.

## Report additions

Each entry under `status_metrics` contains:

- `support`: number of fixtures whose expected label is this status.
- `predicted`: number of fixtures assigned this status by the verifier.
- `true_positive`, `false_positive`, and `false_negative`.
- `precision`, `recall`, and `f1`, using zero when a denominator is zero.

The top-level `macro_f1` is the unweighted mean of F1 across all four statuses.
A status with no examples therefore contributes zero, making coverage gaps visible
rather than silently excluding absent classes. Existing report fields remain
available.

## CLI release gate

Use `--min-macro-f1 0.75` to fail the command when the report's macro F1 is below
the chosen threshold. The accepted range is 0 through 1. This can be combined
with existing filters and `--min-accuracy`; each threshold is evaluated against
the selected fixture subset.

```bash
python -m services.rag.grounding_calibration_cli --min-macro-f1 0.75
python -m services.rag.grounding_calibration_cli --category security --min-accuracy 0.95 --min-macro-f1 0.80
pytest tests/test_rag_grounding_calibration.py tests/test_rag_grounding_calibration_cli_phase66.py
```

These metrics measure agreement with fixture labels, not semantic entailment or
production safety. Choose thresholds based on reviewed fixtures and desired class
coverage; do not treat a high score as proof of factual correctness.

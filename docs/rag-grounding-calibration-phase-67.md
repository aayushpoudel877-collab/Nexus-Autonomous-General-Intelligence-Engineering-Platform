# Phase 67 — Calibration report comparison and regression tracking

Phase 67 adds a deterministic comparison engine for two saved schema-v1
grounding calibration reports. Calibration reports now include a backward-
compatible `case_results` array containing each case ID, fixture filename,
expected status, actual status, and pass/fail outcome. Existing report fields
remain available.

## Compare reports

First save reports from two fixture runs:

```bash
python -m services.rag.calibration_report_diff_cli \
  --baseline baseline.json \
  --current current.json \
  --max-accuracy-drop 0.01 \
  --max-macro-f1-drop 0.02 \
  --max-class-f1-drop 0.03 \
  --max-group-accuracy-drop 0.02
```

The comparison JSON includes deltas for overall accuracy and macro-F1,
per-status precision/recall/F1 and support, category/language group accuracy
and sample counts, plus added/removed cases, newly failing cases, recovered
cases, and changed predictions when both reports contain per-case results.

## Regression gates

By default, any accuracy, macro-F1, per-status F1, or comparable category/language group accuracy decrease fails the command.
Previously passing cases that now fail are also treated as regressions when
per-case data is available.

```bash
python -m services.rag.calibration_report_diff_cli \
  --baseline baseline.json \
  --current current.json \
  --max-accuracy-drop 0.01 \
  --max-macro-f1-drop 0.02 \
  --max-class-f1-drop 0.03 \\\n  --max-group-accuracy-drop 0.02
```

All tolerances must be finite values from 0 to 1. Group accuracy is gated only when a group appears in both reports, so added or removed groups are reported without comparing an absent group as a zero-score group. Invalid JSON, unsupported report
schemas, malformed metric values, duplicate case IDs, and inconsistent case
outcomes return exit status 2. Detected regressions return exit status 1;
a passing comparison returns 0. Use `--allow-new-case-failures` only when case-
level failures are intentionally not a release gate.

## Limitations

Comparison is meaningful only when the reports use comparable fixture sets,
label conventions, and verifier versions. The output surfaces case-set changes
and group sample counts, but it does not normalize distribution shifts or prove
semantic entailment, factual correctness, or production safety. Schema-v1
reports created before Phase 67 remain comparable for aggregate metrics; case-
level analysis is omitted when either report lacks `case_results`.

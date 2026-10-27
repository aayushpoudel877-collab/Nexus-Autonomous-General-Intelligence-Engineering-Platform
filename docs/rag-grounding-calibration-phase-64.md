# Phase 64 — Calibration CLI filters and release threshold

Phase 64 makes the offline grounding calibration runner easier to use in targeted
development and CI jobs. Existing invocations remain supported.

## Filter options

- `--category CATEGORY`: include only a category; may be repeated.
- `--language LANGUAGE`: include only a language; may be repeated.
- `--status STATUS`: include only an expected status; may be repeated.
- `--case-prefix PREFIX`: include only case IDs starting with the prefix.
- `--fixtures PATH`: choose a fixture directory.
- `--output PATH`: write the report to a UTF-8 JSON file, creating parent directories.

When multiple filters are supplied, they combine with AND semantics; repeated values
for one filter use OR semantics. Selecting zero cases is an input error and returns 2.

## Accuracy release gate

Use `--min-accuracy 0.98` to fail the command when measured fixture agreement is
below 98%. The threshold must be in the inclusive range 0 to 1. Existing expected-label
regressions still fail the command regardless of threshold. Exit codes are 0 for a
passing run, 1 for a regression or threshold failure, and 2 for invalid input/loading.

## Examples

```bash
python -m services.rag.grounding_calibration_cli --language ne --language ja
python -m services.rag.grounding_calibration_cli --category security --status grounded
python -m services.rag.grounding_calibration_cli --case-prefix phase63-low-overlap-
python -m services.rag.grounding_calibration_cli --min-accuracy 1.0 --output artifacts/rag-report.json
```

The report is a regression signal for a lexical heuristic, not a semantic-entailment
guarantee. Filtering can also change the sample composition, so compare metrics only
when the selected cohorts are understood and stable.

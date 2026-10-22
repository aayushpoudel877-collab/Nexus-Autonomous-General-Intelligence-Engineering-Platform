# Phase 60 — Calibration breakdowns

Phase 60 adds deterministic per-category and per-language summaries to the offline
RAG grounding calibration report. The global counts, expected-to-actual confusion
counts, and individual failures remain available.

## Report fields

- `breakdown.category`: metrics grouped by fixture category.
- `breakdown.language`: metrics grouped by fixture language.
- Each group reports `case_count`, `passed`, `failed`, and `accuracy`.
- Fixtures that omit a grouping field are included under `unspecified`.
- Group names and confusion entries are sorted for reproducible JSON output.

Each fixture may include non-empty `category` and `language` strings in addition
to the required fields. Invalid optional metadata fails validation instead of
silently corrupting group reports.

## Run

```bash
python -m services.rag.grounding_calibration_cli
pytest tests/test_rag_grounding_calibration.py
```

The report is a regression aid: accuracy measures agreement with expected fixture
labels, not real-world factuality, semantic entailment, or model safety. A high
score can still reflect an incomplete or biased corpus. Review category-level
and language-level sample counts alongside the accuracy values, and do not
interpret a small group as statistically conclusive.

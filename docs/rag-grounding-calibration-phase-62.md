# Phase 62 — Grounding calibration boundaries and Unicode

Phase 62 expands the offline grounding calibration corpus with 50 cases focused on
decision boundaries and input diversity.

## New coverage

- 10 intermediate-overlap cases expected to remain `inconclusive`, avoiding a
  forced binary decision when lexical evidence is neither strong nor negligible.
- 10 claims with no citations, expected to be unsupported even when an unrelated
  evidence record is available.
- 15 exact-match Unicode cases spanning Nepali, Japanese, Arabic, Cyrillic,
  Spanish, French, German, Portuguese, Italian, Indonesian, Thai, Korean,
  Chinese, and Vietnamese text.
- 15 low-overlap cases across platform domains, expected to be unsupported.

## Validation

Run the calibration suite and the CLI:

```bash
pytest tests/test_rag_grounding_calibration.py tests/test_rag_grounding_calibration_phase62.py
python -m services.rag.grounding_calibration_cli
```

The suite checks expected behavior of a lexical heuristic. Exact-match results in
a language do not establish multilingual semantic understanding, and these
fixtures are not a substitute for human-reviewed entailment evaluation.

# Phase 63 — Calibration reporting and boundary regression corpus

Phase 63 adds 50 offline regression fixtures to the grounding calibration corpus.
The cases exercise exact lexical matches, Unicode strings, punctuation and numeric
text, metadata groupings, citation-free claims, and low-overlap evidence.

## Expected distribution

- 43 cases expect `grounded` for exact lexical matches.
- 7 cases expect `unsupported` for missing citations or deliberately unrelated evidence.
- All cases declare a category and language to exercise grouped reporting.

## Validation

```bash
pytest tests/test_rag_grounding_calibration.py tests/test_rag_grounding_calibration_phase62.py tests/test_rag_grounding_calibration_phase63.py
python -m services.rag.grounding_calibration_cli
```

The test also compares confusion matrices and grouped breakdowns when input order
is reversed. The evaluator sorts its report keys so summaries remain deterministic.

## Interpretation boundary

This is a regression suite for a lexical heuristic. Exact text matches, Unicode
preservation, and fixture agreement do not prove semantic entailment, factual
correctness, or multilingual understanding. Production decisions should retain
source review and appropriate human evaluation.

# Phase 65 — Grounding fixture schema hardening

Phase 65 strengthens validation at the boundary of the offline calibration corpus.
It rejects empty citation identifiers, repeated citation identifiers, duplicate
evidence identifiers, blank evidence IDs, and blank evidence text. Invalid data
fails early with a specific message rather than entering the verifier and producing
ambiguous metrics.

## Validation contract

- Citations must be a list of unique, non-empty strings.
- Evidence must remain a non-empty list of objects.
- Every evidence object must contain a unique, non-empty string `evidence_id`.
- Every evidence object must contain non-empty string `text`.
- Existing case identifiers, claim text, expected labels, and optional grouping
  metadata retain their validation rules.

Run focused tests with:

```bash
pytest tests/test_rag_grounding_calibration.py
pytest tests/test_rag_grounding_calibration_cli_phase64.py
```

This is fixture-input validation, not a claim that the lexical verifier understands
meaning or that its output proves semantic entailment.

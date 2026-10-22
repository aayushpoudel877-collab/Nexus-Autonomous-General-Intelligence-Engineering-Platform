# Phase 61 — Grounding calibration diversity corpus

Phase 61 expands the offline calibration corpus with 50 additional cases designed
to exercise the verifier's three high-confidence lexical outcomes across core
platform domains.

## Coverage added

- 20 exact-overlap cases expected to be labelled `grounded`.
- 15 low-overlap cases expected to be labelled `unsupported`.
- 15 strong-overlap cases with a negation-marker mismatch expected to be labelled
  `contradictory`.
- Cases are tagged by category so the Phase 60 breakdown report can expose
  domain-specific regressions.
- Each fixture is independently stored as JSON and loaded by the existing corpus
  loader, preserving deterministic file ordering and duplicate-ID validation.

## Run

```bash
python -m services.rag.grounding_calibration_cli
pytest tests/test_rag_grounding_calibration.py
```

The new cases test deterministic lexical behavior, not semantic entailment. In
particular, adding a negation marker is a narrow heuristic regression probe and
does not prove that natural-language contradictions are reliably understood.
Review the full report and failures; do not treat corpus accuracy as a production
safety or factuality guarantee.

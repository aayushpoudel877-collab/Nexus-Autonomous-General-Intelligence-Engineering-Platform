# Phase 58 — Grounding Calibration Regression Corpus

## Goal

Keep the existing lexical claim-grounding baseline stable with a deterministic,
reviewable corpus of expected outcomes. Each JSON fixture is a separate
regression vector so a failing case can be identified and changed independently.

## Run locally

```bash
python -m pytest tests/test_rag_grounding_calibration.py -q
python -m services.rag.grounding_calibration_cli
python -m services.rag.grounding_calibration_cli --output grounding-calibration-report.json
```

The CLI returns exit code 0 when every case agrees with its expected label, 1
when a regression is found, and 2 when the corpus cannot be loaded or validated.
The report contains case counts, accuracy, a sorted expected-to-actual confusion
summary, and the exact fixture names that disagree.

## Fixture contract

Every case contains a unique `case_id`, non-empty `claim`, `citations` list,
non-empty `evidence` list, and `expected_status`. Evidence items contain
`evidence_id` and `text`. Supported labels are `grounded`, `unsupported`,
`contradictory`, and `inconclusive`.

## Interpretation and limitations

The corpus tests deterministic behavior, not factual truth. A lexical match is
not proof of semantic entailment, and an unsupported lexical result is not proof
that no evidence exists. Keep human-reviewed multilingual benchmarks separate
from synthetic or hand-authored contract fixtures. Never use this score alone
as a production release or safety decision.

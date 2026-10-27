# Grounding calibration fixtures

Each `.json` file is one independently named regression case consumed by
`services.rag.grounding_calibration.load_case_files`. Keep identifiers stable,
use UTF-8, and update the expected label only when the behavior change is
reviewed. These fixtures exercise lexical verifier contracts; they are not a
semantic-entailment benchmark.

Required fields: `case_id`, `claim`, `citations`, `evidence`, and
`expected_status`. Evidence is a list of objects with `evidence_id` and
`text`. Use exact lexical matches for supported cases and disjoint vocabulary
for unsupported cases unless the fixture intentionally tests a more specific
heuristic.

## Phase 62 additions

The `phase62-*.json` fixtures add 50 cases covering intermediate lexical
overlap, claims without citations, exact-match Unicode text, and low-overlap
evidence. Use `tests/test_rag_grounding_calibration_phase62.py` to validate the
expected outcome distribution. Exact-match Unicode cases check tokenizer
consistency only; they do not demonstrate semantic understanding of a language.

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

## Phase 63 additions

The `phase63-*.json` fixtures add 50 regression cases for exact lexical matches, Unicode text, punctuation and numeric tokens, metadata grouping, citation-free claims, and low-overlap evidence. Validate their label distribution and deterministic report breakdowns with `tests/test_rag_grounding_calibration_phase63.py`. These remain lexical regression fixtures, not a semantic-entailment benchmark.

## Phase 64 additions

Phase 64 adds CLI filters for category, language, expected status, and case-ID prefix, plus a minimum-accuracy gate. Filtered runs that select no fixtures fail explicitly. See `docs/rag-grounding-calibration-phase-64.md` for filter composition, examples, and exit-code semantics; tests are in `tests/test_rag_grounding_calibration_cli_phase64.py`.

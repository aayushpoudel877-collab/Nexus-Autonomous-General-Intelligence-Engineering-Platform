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

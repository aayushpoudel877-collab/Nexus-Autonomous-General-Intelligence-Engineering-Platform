# RAG Evaluation Protocol

## Dataset format
Maintain a versioned JSONL set with one record per query: `case_id`, `tenant_id`, `query`, `relevant_chunk_ids`, expected answer claims, required source IDs, language, risk category, and reviewer notes. Do not include production personal data in fixtures.

## Retrieval metrics
- Recall@k = relevant retrieved chunks / all known relevant chunks.
- Reciprocal rank = 1 / rank of the first relevant chunk, or zero if none is found.
- Also report empty-result rate, per-tenant isolation tests, and latency percentiles.

## Answer metrics
- Citation coverage: fraction of factual answer claims with citations.
- Citation validity: citations refer to evidence actually provided to the generator.
- Faithfulness: human-reviewed support/entailment of each claim by cited evidence.
- Completeness: required answer points present without irrelevant material.
- Abstention quality: system says evidence is insufficient when appropriate.
- Robustness: prompt-injection, conflicting sources, stale documents, multilingual spelling, and near-duplicate cases.

## Release gate
A retrieval/ranking change must be compared against the previous baseline on the same dataset. Report aggregate and slice-level metrics. No aggregate gain may hide a material regression in tenant isolation, safety, language coverage, or high-risk categories. Structural citation validation is necessary but not sufficient for factual grounding.

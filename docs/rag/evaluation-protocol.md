# RAG Evaluation Protocol

## Dataset format
Maintain a versioned JSONL set with one record per query: `case_id`, `tenant_id`, `query`, `relevant_chunk_ids`, expected answer claims, required source IDs, language, risk category, and reviewer notes. Do not include production personal data in fixtures.

## Retrieval metrics
- Precision@k = relevant retrieved chunks divided by requested k.
- Recall@k = relevant retrieved chunks divided by all known relevant chunks.
- Reciprocal rank = 1 / rank of the first relevant chunk, or zero if none is found.
- NDCG@k discounts relevant results lower in the ranked list.
- Also report empty-result rate, per-tenant isolation tests, and latency percentiles.
- Compare each strategy per query, then average over the same judged query set; a missing ranking counts as an empty result.

## Ranking experiment record
Record the dataset version/hash, query set, tenant filter, candidate-generation source, BM25 k1/b, lexical/dense weights, RRF rank constant and weights, diversity limit, top-k, code revision, and environment. Keep a baseline run unchanged. Separate tuning data from final evaluation data and do not claim a ranking improvement until results have been computed on a reviewed dataset.

## Answer metrics
- Citation coverage: fraction of factual answer claims with citations.
- Citation validity: citations refer to evidence actually provided to the generator.
- Faithfulness: human-reviewed support/entailment of each claim by cited evidence.
- Completeness: required answer points present without irrelevant material.
- Abstention quality: system says evidence is insufficient when appropriate.
- Robustness: prompt-injection, conflicting sources, stale documents, multilingual spelling, and near-duplicate cases.

## Release gate
A retrieval/ranking change must be compared against the previous baseline on the same dataset. Report aggregate and slice-level metrics. No aggregate gain may hide a material regression in tenant isolation, safety, language coverage, or high-risk categories. Structural citation validation is necessary but not sufficient for factual grounding.


## Claim-grounding baseline (Phase 33)

Represent each answer claim as a separate record with a stable `claim_id`, non-empty
claim text, and the exact evidence IDs cited for that claim. Claim segmentation is
currently supplied by the caller; do not assume sentence splitting is equivalent to
factual-claim extraction. Reject duplicate claim IDs, duplicate evidence IDs, and
citations that are absent from the evidence set.

The deterministic `LexicalGroundingVerifier` reports one of four statuses:

- **grounded** — cited evidence reaches the configured lexical token-coverage threshold and the simple negation-marker check does not detect a mismatch;
- **unsupported** — the claim has no citation or the best cited passage has low lexical coverage;
- **contradictory** — strong lexical overlap exists but a simple negation-marker mismatch is detected;
- **inconclusive** — lexical coverage falls between the configured thresholds.

The default thresholds are 0.75 for strong overlap and 0.25 for low overlap. They are
engineering defaults, not empirically calibrated confidence values. The negation check
is intentionally shallow: it does not resolve scope, modality, dates, quantities,
coreference, synonyms, or domain-specific contradictions. A grounded label is therefore
only a lexical signal, not semantic entailment or factual verification.

The report includes claim counts by status, citation coverage, a strict grounded-claim
rate, and `should_abstain`. The baseline recommends abstention whenever the claim set
is empty or any claim is not classified as grounded. Applications must decide how to
present mixed-support answers and should not silently drop unsupported claims.

For release evaluation, add human-reviewed labels for support, contradiction, and
abstention quality; retain difficult examples and language/risk slices; report confusion
matrices and per-slice precision/recall; and compare any future model-backed verifier
against this deterministic baseline on the same fixed dataset. Do not claim semantic
grounding improvements from lexical metrics alone.

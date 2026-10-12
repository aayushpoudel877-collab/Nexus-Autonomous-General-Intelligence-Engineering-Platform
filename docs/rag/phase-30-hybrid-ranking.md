# Phase 30 — Hybrid ranking and retrieval evaluation

## Delivered in this phase

- Parameterized BM25 scoring (`k1` and `b`) with input validation and normalized lexical scores.
- Optional document allowlists and denylists applied after tenant scoping.
- Optional per-document result caps to reduce repetitive chunks from a single source.
- Finite/range validation for supplied dense similarity values.
- Reciprocal-rank fusion (RRF) for combining independently ranked lists, with configurable weights, rank constant and result count.
- Reusable score filters and group-based diversity selection.
- Offline binary relevance metrics: precision@k, recall@k, mean reciprocal rank and NDCG@k.
- Query-level comparison of named ranking runs to support ablation reports.
- Deterministic tests for invalid settings, tie-breaking, duplicate candidates, filtering, source diversity, metric calculation and tenant isolation.

## Retrieval behavior

The existing `hybrid_retrieve` API keeps its prior defaults. New optional parameters allow experiments to tune BM25, constrain results to a set of document IDs, exclude documents, and cap results per document. Tenant filtering is applied first and remains mandatory.

RRF is a standalone utility because lexical and dense providers may produce different candidate lists. Callers should generate each ranked list from the same authorized candidate scope, then fuse the lists. These utilities do not authorize access to documents and must not be used to broaden tenant scope.

## Evaluation usage

Create one relevance set per query and supply a separate ranked list for each named strategy and query. Metrics are averaged across the judged query set. Missing query results count as an empty ranking. Keep the golden query set stable across experiments and report the dataset version, candidate-generation settings and rank parameters alongside metrics.

## Safety and limitations

- Relevance judgments are binary; graded relevance and inter-annotator agreement are not implemented.
- The metric harness does not create or certify a golden dataset.
- RRF does not replace tenant authorization or source filtering.
- This phase does not wire a hosted embedding provider or durable vector database into the API.
- Ranking gains must be measured on reviewed data; no quality improvement is claimed without benchmark results.

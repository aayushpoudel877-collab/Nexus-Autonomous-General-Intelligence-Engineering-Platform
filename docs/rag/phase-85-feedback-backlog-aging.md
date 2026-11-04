# RAG Phase 85 — Feedback backlog aging

Phase 85 adds a role-gated, tenant-scoped endpoint for unresolved feedback age. It classifies records in the `new` and `triaged` states into four rolling UTC age bands (under 24 hours, 1–7 days, 7–30 days, and over 30 days). Aggregation and age classification happen in the database, and all four buckets are returned even when empty.

The RAG Operator Workbench shows open, new, and triaged totals plus a status breakdown by age band. Resolved and ignored records are excluded. No individual feedback fields are returned and no schema migration is introduced.

Backlog age is an operational workload signal only. It is not a measure of retrieval relevance, factual correctness, or answer quality.

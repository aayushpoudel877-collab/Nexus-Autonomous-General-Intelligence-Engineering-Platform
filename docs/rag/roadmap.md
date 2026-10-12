# RAG Knowledge Intelligence Roadmap

**Phase numbering is local to the RAG subsystem** and is independent of the platform-wide phase numbers in `docs/roadmap.md`.

This is a multi-phase research and engineering program. A large commit count is not a quality metric; changes should represent reviewable, tested improvements.

- **Phase 26 — Retrieval core (implemented):** contracts, normalization/chunking, tenant-scoped lexical retrieval, optional dense-score fusion, evidence packaging, citation structure checks, baseline metrics and tests.
- **Phase 27 — Persistent corpus (implemented foundation):** organization-owned document/chunk models, PostgreSQL migration, content SHA-256 deduplication, lifecycle status, bounded pagination, async persistence helpers, concurrent duplicate handling and contract tests.
- **Phase 28 — Authenticated RAG API (implemented foundation):** authenticated and role-gated ingestion, tenant-scoped listing/chunk reads/logical deletion, bounded lexical query endpoint, audit events, strict request schemas, API contract tests and security documentation.
- **Phase 29 — Embedding adapters (contract foundation implemented):** provider-neutral model/version contracts, bounded async batching, finite/dimension validation, tenant-scoped LRU cache, vector-store protocol, test-only cosine reference backend and contract tests. Concrete provider SDKs, provider-specific rate limiting/retries, durable vector indexing, API integration and PostgreSQL/pgvector migration tests remain open acceptance items.
- **Phase 30 — Hybrid ranking research (foundation implemented):** tunable BM25, weighted reciprocal-rank fusion, document filters, source diversity limits, precision/recall/MRR/NDCG metrics and query-level ranking comparisons. Reviewed datasets, query rewriting experiments and measured ablation reports remain future work.
- **Phase 31 — Document ingestion (foundation implemented):** bounded multipart uploads; allowlisted TXT/Markdown/HTML/PDF/DOCX extraction; MIME/extension and PDF/DOCX container checks; text/byte limits; parser provenance; authenticated role-gated persistence; upload audit details and parser unit tests. Malware scanning/quarantine, durable dead-letter retries, OCR, PostgreSQL endpoint integration tests and extraction-quality benchmarks remain open.
- **Phase 32 — Generation adapters (orchestration foundation implemented):** provider-neutral async contract, strict JSON answer schema, evidence-ID citation validation, explicit prompt versioning, bounded context/input/output/answer budgets, timeout and capped transient retries, usage checks, canonical abstention and contract tests. Concrete provider SDKs, exact cost ledger, API integration, streaming, and claim-entailment validation remain future work.
- **Phase 33 — Semantic grounding:** claim segmentation, quote/span alignment, contradiction checks, and reviewed entailment benchmarks.
- **Phase 34 — Evaluation harness:** curated golden sets, regression thresholds, synthetic query generation with review, offline reports and CI gates.
- **Phase 35 — Observability and governance:** privacy-safe traces, source lineage, deletion propagation, audit events, model cards and data governance.
- **Phase 36 — Operator workbench:** ingestion health, retrieval traces, feedback triage, dataset review and controlled reindexing.
- **Phase 37+ — Advanced research:** multilingual and low-resource retrieval, multimodal indexing, graph-assisted retrieval, agentic retrieval with bounded tool access, and robust prompt-injection evaluation.

A phase is complete only when its acceptance criteria, tests, documentation, and security review are recorded. Avoid artificial commits; use focused commits for meaningful increments.

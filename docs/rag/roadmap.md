# RAG Knowledge Intelligence Roadmap

This is a multi-phase research and engineering program. A large commit count is not a quality metric; changes should represent reviewable, tested improvements.

- **Phase 26 — Retrieval core (current):** contracts, normalization/chunking, lexical retrieval, optional dense-score fusion, evidence packaging, citation structure checks, baseline metrics and tests.
- **Phase 27 — Persistent corpus:** PostgreSQL document/chunk schemas, tenant-safe migrations, lifecycle states, idempotent ingestion, content hashes and retention controls.
- **Phase 28 — Embedding adapters:** pluggable embedding interface, batching, rate limits, model/version tracking, vector store abstraction and migration tests.
- **Phase 29 — Hybrid ranking research:** configurable BM25, reciprocal-rank fusion, query rewriting experiments, metadata filters, diversity controls and ablation reports.
- **Phase 30 — Ingestion pipeline:** bounded PDF/DOCX/HTML/text parsers, MIME validation, malware scanning integration, extraction provenance and dead-letter handling.
- **Phase 31 — RAG API integration:** authenticated endpoints, tenant context propagation, request correlation, pagination and rate limits.
- **Phase 32 — Generation adapters:** provider-neutral interface, structured outputs, timeouts, retries, budget controls, refusal/abstention behavior and prompt versioning.
- **Phase 33 — Semantic grounding:** claim segmentation, quote/span alignment, contradiction checks, and reviewed entailment benchmarks.
- **Phase 34 — Evaluation harness:** curated golden sets, regression thresholds, synthetic query generation with review, offline reports and CI gates.
- **Phase 35 — Observability and governance:** privacy-safe traces, source lineage, deletion propagation, audit events, model cards and data governance.
- **Phase 36 — Operator workbench:** ingestion health, retrieval traces, feedback triage, dataset review and controlled reindexing.
- **Phase 37+ — Advanced research:** multilingual and low-resource retrieval, multimodal indexing, graph-assisted retrieval, agentic retrieval with bounded tool access, and robust prompt-injection evaluation.

A phase is complete only when its acceptance criteria, tests, documentation, and security review are recorded. Avoid artificial commits; use focused commits for meaningful increments.

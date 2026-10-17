# NEXUS RAG Intelligence Engine

A tenant-aware Retrieval-Augmented Generation (RAG) subsystem for NEXUS-Ω. The current foundation includes deterministic retrieval, source attribution, persistent document/chunk records, and evaluation hooks. It is provider-independent and treats retrieved text as untrusted data.

## Capabilities
- Unicode-aware NFC text tokenization and overlap-aware chunking with source offsets.
- Multilingual lexical token support for scripts including Devanagari, Arabic, Cyrillic, Japanese, and Latin diacritics.
- Opt-in character n-gram retrieval weighting for scripts without reliable whitespace segmentation; default weight is zero, and this remains a lexical—not semantic—signal.
- Tenant-scoped document and chunk contracts.
- Hybrid lexical retrieval with optional externally generated dense similarity scores.
- Evidence packaging, citation-reference validation, and retrieval metrics.
- Validated multimodal text representations with source provenance, credential-like metadata filtering, and collision-safe representation IDs; OCR/transcription providers remain unconnected.
- Bounded graph-assisted retrieval over explicit tenant-scoped entity/chunk associations, with deterministic paths and limits on seeds, edges, entities, associations, and hops.
- Offline prompt-injection marker evaluation with false-positive/false-negative reporting and language/risk slices; it is a heuristic, not a security boundary.
- PostgreSQL-backed document/chunk schema and async persistence helpers.
- Content-hash idempotency per organization and lifecycle states for documents.
- Privacy-safe audit event, source lineage, deletion-outbox, retention, and model-card governance contracts with tests.

## Boundaries
The RAG API and ingestion foundations exist, but concrete hosted embedding/generation providers and durable external vector indexing remain separate integration tasks. Phase 35 governance helpers define contracts only: they do not emit telemetry, physically delete external index records, run retention jobs, or approve model cards. The API must derive organization scope from authenticated membership and own transaction commits. Citation checks and lexical grounding signals do not prove semantic entailment. Treat retrieved text as untrusted data, never as instructions.

## Quick start
From the repository root:

```bash
python -m pytest services/rag/tests tests/test_rag_persistence_contracts.py -q
python -m services.rag.demo
```

Apply database migrations with the repository's normal Alembic workflow before using persistence in a deployed API.

See `docs/rag/phase-26-architecture.md`, `docs/rag/phase-27-persistent-corpus.md`, `docs/rag/phase-37-multilingual-low-resource.md`, `docs/rag/phase-38-multimodal-ingestion-quality.md`, `docs/rag/phase-39-graph-assisted-retrieval-hardening.md`, `docs/rag/phase-40-prompt-injection-evaluation.md`, `docs/rag/phase-43-untrusted-tool-output.md`, `docs/rag/phase-44-tool-output-provenance.md`, `docs/rag/phase-45-safe-provenance-serialization.md`, `docs/rag/phase-46-tool-provenance-audit-bridge.md`, `docs/rag/phase-47-checksummed-audit-envelopes.md`, `docs/rag/phase-48-execution-boundary-audit-hook.md`, `docs/rag/phase-49-database-tool-audit-writer.md`, and `docs/rag/roadmap.md`.

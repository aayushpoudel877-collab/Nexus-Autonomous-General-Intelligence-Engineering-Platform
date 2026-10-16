# NEXUS RAG Intelligence Engine

A tenant-aware Retrieval-Augmented Generation (RAG) subsystem for NEXUS-Ω. The current foundation includes deterministic retrieval, source attribution, persistent document/chunk records, and evaluation hooks. It is provider-independent and treats retrieved text as untrusted data.

## Capabilities
- Unicode-aware NFC text tokenization and overlap-aware chunking with source offsets.
- Multilingual lexical token support for scripts including Devanagari, Arabic, Cyrillic, Japanese, and Latin diacritics.
- Opt-in character n-gram retrieval weighting for scripts without reliable whitespace segmentation; default weight is zero, and this remains a lexical—not semantic—signal.
- Tenant-scoped document and chunk contracts.
- Hybrid lexical retrieval with optional externally generated dense similarity scores.
- Evidence packaging, citation-reference validation, and retrieval metrics.
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

See `docs/rag/phase-26-architecture.md`, `docs/rag/phase-27-persistent-corpus.md`, `docs/rag/phase-37-multilingual-low-resource.md`, and `docs/rag/roadmap.md`.

# NEXUS RAG Intelligence Engine

A tenant-aware Retrieval-Augmented Generation (RAG) subsystem for NEXUS-Ω. The current foundation includes deterministic retrieval, source attribution, persistent document/chunk records, and evaluation hooks. It is provider-independent and treats retrieved text as untrusted data.

## Capabilities
- Stable text normalization and overlap-aware chunking with source offsets.
- Tenant-scoped document and chunk contracts.
- Hybrid lexical retrieval with optional externally generated dense similarity scores.
- Evidence packaging, citation-reference validation, and retrieval metrics.
- PostgreSQL-backed document/chunk schema and async persistence helpers.
- Content-hash idempotency per organization and lifecycle states for documents.
- Unit tests, a local retrieval demo, architecture/security notes, and a staged research roadmap.

## Boundaries
This subsystem does **not** yet generate embeddings, query a vector database, parse uploaded binary files, call an LLM, or expose a public API. The API must derive organization scope from authenticated membership and own transaction commits. Citation checks validate reference structure, not semantic entailment. Treat retrieved text as untrusted data, never as instructions.

## Quick start
From the repository root:

```bash
python -m pytest services/rag/tests tests/test_rag_persistence_contracts.py -q
python -m services.rag.demo
```

Apply database migrations with the repository's normal Alembic workflow before using persistence in a deployed API.

See `docs/rag/phase-26-architecture.md`, `docs/rag/phase-27-persistent-corpus.md`, and `docs/rag/roadmap.md`.

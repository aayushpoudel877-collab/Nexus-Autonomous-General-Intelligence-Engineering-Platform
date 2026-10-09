# NEXUS RAG Intelligence Engine — Phase 26

A tenant-aware Retrieval-Augmented Generation (RAG) subsystem for NEXUS-Ω. This phase establishes a deterministic, provider-agnostic retrieval core with explicit source attribution and evaluation hooks. It is intentionally safe by default: no hidden web fetching, no arbitrary code execution, and no claim that retrieved text is trustworthy instructions.

## Capabilities in this phase
- Stable text normalization and overlap-aware chunking with source offsets.
- Tenant-scoped document and chunk contracts.
- Hybrid lexical retrieval using a transparent BM25-like scorer plus optional dense-vector scores.
- Rank fusion, duplicate suppression, source diversity, and evidence packaging.
- Citation validation that rejects references to chunks not present in the supplied evidence.
- Evaluation primitives for recall@k, reciprocal rank, citation coverage, and unsupported-answer flags.
- A small deterministic demo path that does not require API keys or a hosted model.

## Boundaries
This package does **not** yet embed documents, call an LLM, persist vectors, parse binary files, or perform production authorization by itself. Integrate it through NEXUS API authentication and tenant context. Dense scores must come from a separately configured embedding/vector adapter. Treat all retrieved content as untrusted data, not instructions.

## Quick start
From the repository root:

```bash
python -m pytest services/rag/tests -q
python -m services.rag.demo
```

See `docs/rag/phase-26-architecture.md` for design and `docs/rag/roadmap.md` for follow-on milestones.

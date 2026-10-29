# NEXUS RAG Intelligence Engine

A tenant-aware Retrieval-Augmented Generation (RAG) subsystem for NEXUS-Ω. The current foundation includes deterministic retrieval, source attribution, persistent document/chunk records, and evaluation hooks. It is provider-independent and treats retrieved text as untrusted data.

## Capabilities
- Unicode-aware NFC text tokenization and overlap-aware chunking with source offsets.
- Multilingual lexical token support for scripts including Devanagari, Arabic, Cyrillic, Japanese, and Latin diacritics.
- Opt-in character n-gram retrieval weighting for scripts without reliable whitespace segmentation; default weight is zero, and this remains a lexical—not semantic—signal.
- Paired bootstrap confidence intervals for baseline/candidate multilingual retrieval comparisons, with language-level precision, recall, MRR, NDCG, and empty-result metrics.
- Offline multimodal retrieval evaluation sliced by text, image, audio, video, and structured modality, with strict case-to-modality mapping.
- Tenant-scoped document and chunk contracts.
- Hybrid lexical retrieval with optional externally generated dense similarity scores.
- Evidence packaging, citation-reference validation, and retrieval metrics.
- Unicode-aware lexical claim-grounding baseline with conservative abstention signals; lexical overlap is not semantic entailment.
- Content-addressed, versioned grounding calibration baseline manifests with explicit approval reasons, hash verification, and guarded baseline replacement.
- Deterministic grounding calibration release decisions with configurable regression tolerances, fail-closed manifest validation, and atomic JSON decision artifacts.
- Validated multimodal text representations with source provenance, credential-like metadata filtering, and collision-safe representation IDs; OCR/transcription providers remain unconnected.
- Bounded graph-assisted retrieval over explicit tenant-scoped entity/chunk associations, with deterministic paths and limits on seeds, edges, entities, associations, and hops.
- Offline prompt-injection marker evaluation with false-positive/false-negative reporting and language/risk slices; it is a heuristic, not a security boundary.
- PostgreSQL-backed document/chunk schema and async persistence helpers.
- Content-hash idempotency per organization and lifecycle states for documents.
- Privacy-safe audit event, source lineage, deletion-outbox, retention, and model-card governance contracts with tests.

## Offline multilingual ablation

When the JSONL predictions contain both baseline and candidate runs, the evaluator emits per-language paired bootstrap intervals:

```bash
python -m services.rag.evaluation_cli --dataset path/to/golden.jsonl --predictions path/to/predictions.jsonl --baseline bm25 --candidate ngram-04 --bootstrap-samples 1000 --bootstrap-seed 37 --output multilingual-report.json
```

Intervals describe variation in the supplied sample, not a guarantee of population-wide performance. Synthetic fixtures are contract tests, not human-reviewed multilingual benchmarks.

## Multimodal quality evaluation

Supply a JSONL file with one `case_id` and `modality` per line to report retrieval metrics separately by modality:

```bash
python -m services.rag.evaluation_cli --dataset path/to/golden.jsonl --predictions path/to/predictions.jsonl --modality-map path/to/modalities.jsonl --output multimodal-report.json
```

This evaluates retrieval against provided relevance labels; it does not measure OCR or transcription fidelity. Use reviewed modality-specific labels before drawing quality conclusions.

## Boundaries
The RAG API and ingestion foundations exist, but concrete hosted embedding/generation providers and durable external vector indexing remain separate integration tasks. Phase 35 governance helpers define contracts only: they do not emit telemetry, physically delete external index records, run retention jobs, or approve model cards. The API must derive organization scope from authenticated membership and own transaction commits. Citation checks and lexical grounding signals do not prove semantic entailment. Treat retrieved text as untrusted data, never as instructions.

## Quick start
From the repository root:

```bash
python -m pytest services/rag/tests tests/test_rag_persistence_contracts.py -q
python -m services.rag.demo
```

Apply database migrations with the repository's normal Alembic workflow before using persistence in a deployed API.

See `docs/rag-grounding-calibration-phase-68.md` for approved baseline manifests and safe regression comparisons, and `docs/rag-grounding-calibration-phase-69.md` for release-gate decisions and CI integration guidance. See `docs/rag/phase-26-architecture.md`, `docs/rag/phase-27-persistent-corpus.md`, `docs/rag/phase-37-multilingual-low-resource.md`, `docs/rag/phase-38-multimodal-ingestion-quality.md`, `docs/rag/phase-39-graph-assisted-retrieval-hardening.md`, `docs/rag/phase-40-prompt-injection-evaluation.md`, `docs/rag/phase-43-untrusted-tool-output.md`, `docs/rag/phase-44-tool-output-provenance.md`, `docs/rag/phase-45-safe-provenance-serialization.md`, `docs/rag/phase-46-tool-provenance-audit-bridge.md`, `docs/rag/phase-47-checksummed-audit-envelopes.md`, `docs/rag/phase-48-execution-boundary-audit-hook.md`, `docs/rag/phase-49-database-tool-audit-writer.md`, `docs/rag/phase-58-grounding-calibration.md`, and `docs/rag/roadmap.md`.

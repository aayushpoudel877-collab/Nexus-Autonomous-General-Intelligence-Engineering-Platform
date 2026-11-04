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
- Reproducible calibration provenance sidecars binding reports to source revisions, evaluator identifiers, and exact input-file hashes; provenance is not approval.
- Deterministic grounding calibration release decisions with configurable regression tolerances, fail-closed manifest validation, atomic JSON decision artifacts, and default rejection of calibration case-set drift.
- Validated multimodal text representations with source provenance, credential-like metadata filtering, and collision-safe representation IDs; OCR/transcription providers remain unconnected.
- Bounded graph-assisted retrieval over explicit tenant-scoped entity/chunk associations, with deterministic paths and limits on seeds, edges, entities, associations, and hops.
- Offline prompt-injection marker evaluation with false-positive/false-negative reporting and language/risk slices; it is a heuristic, not a security boundary.
- PostgreSQL-backed document/chunk schema and async persistence helpers.
- Content-hash idempotency per organization and lifecycle states for documents.
- Privacy-safe audit event, source lineage, deletion-outbox, retention, and model-card governance contracts with tests.
- Calibration release governance that verifies active approval-ledger entries and authenticated GitHub pull-request reviews against the exact attested source revision.
- Trusted GitHub review ingestion is resource-bounded by per-response byte, total-review, and pagination limits; oversized evidence fails closed.
- Governed release decisions include deterministic, UTC-normalized receipts of the latest allowlisted GitHub review states and a canonical SHA-256 evidence digest; duplicate review IDs fail closed.
- Governed-release evaluation independently validates a versioned review receipt, recomputes its digest, checks decision/approval consistency, and rejects tampered or unknown receipt fields.
- Offline review-receipt CLI reuses the strict verifier for saved JSON artifacts, applies a 1 MB input bound, rejects malformed/non-finite JSON, and emits a compact machine-readable result.
- Authenticated GitHub review ingestion strictly decodes UTF-8 JSON, rejects duplicate keys/non-finite numbers, and validates the pull-request response shape before pagination.

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

See `docs/rag-grounding-calibration-phase-77.md` for strict versioned review-receipt verification and `docs/rag-grounding-calibration-phase-76.md` for deterministic trusted review receipts, `docs/rag-grounding-calibration-phase-75.md` for bounded trusted review ingestion, and `docs/rag-grounding-calibration-phase-74.md` for trusted GitHub reviewer verification and governed release enforcement, `docs/rag-grounding-calibration-phase-73.md` for approval lifecycle, `docs/rag-grounding-calibration-phase-72.md` for approval governance, and `docs/rag-grounding-calibration-phase-71.md` for report provenance attestations. See `docs/rag-grounding-calibration-phase-68.md` for approved baseline manifests, `docs/rag-grounding-calibration-phase-69.md` for release-gate decisions and CI integration, and `docs/rag-grounding-calibration-phase-70.md` for case-set drift policy. See `docs/rag/phase-26-architecture.md`, `docs/rag/phase-27-persistent-corpus.md`, `docs/rag/phase-37-multilingual-low-resource.md`, `docs/rag/phase-38-multimodal-ingestion-quality.md`, `docs/rag/phase-39-graph-assisted-retrieval-hardening.md`, `docs/rag/phase-40-prompt-injection-evaluation.md`, `docs/rag/phase-43-untrusted-tool-output.md`, `docs/rag/phase-44-tool-output-provenance.md`, `docs/rag/phase-45-safe-provenance-serialization.md`, `docs/rag/phase-46-tool-provenance-audit-bridge.md`, `docs/rag/phase-47-checksummed-audit-envelopes.md`, `docs/rag/phase-48-execution-boundary-audit-hook.md`, `docs/rag/phase-49-database-tool-audit-writer.md`, `docs/rag/phase-58-grounding-calibration.md`, and `docs/rag/roadmap.md`.


## Offline review-receipt verification

Verify a saved Phase 77 GitHub review receipt without contacting GitHub:

```bash
python -m services.rag.calibration_review_receipt_cli --receipt review-receipt.json
```

This checks receipt structure, policy consistency, and its canonical digest. It does not authenticate the artifact's origin or refresh live GitHub approval status. See `docs/rag-grounding-calibration-phase-78.md`.


## Trusted GitHub API response validation

The review-governance transport rejects duplicate JSON keys, non-finite numeric constants, malformed UTF-8/JSON, and invalid pull-request response shapes while retaining existing response-size and pagination limits. See `docs/rag-grounding-calibration-phase-79.md`.


## Bounded offline review-receipt verification

Offline review receipt verification enforces the same 10,000-review ceiling as live GitHub ingestion for both serialized decisions and the aggregate review count. Over-limit receipts are rejected before decision traversal and digest verification. See `docs/rag-grounding-calibration-phase-80.md`.


## Guided RAG Studio

The web app provides a guided `/rag-studio` workspace for adding TXT, Markdown, HTML, PDF, and DOCX sources or pasting text, browsing the active organization-scoped library, querying with lexical retrieval, expanding evidence passages, and submitting usefulness feedback. The interface reports synchronous ingestion and lexical retrieval accurately; it does not present retrieved passages as generated answers or ranking scores as factual confidence. See `docs/rag-grounding-calibration-phase-81.md`.


## Feedback insights

The operator workbench displays tenant-scoped aggregate feedback counts and helpful-rate summaries from the existing privacy-conscious feedback records. The summary endpoint returns aggregate values only and does not expose raw query text, digests, notes, actors, or evidence IDs. Helpful ratings describe user-perceived usefulness, not factual correctness. See `docs/rag-feedback-insights-phase-82.md`.


## Feedback activity trends

The RAG Operator Workbench can display daily helpful/unhelpful feedback counts over a bounded 7–90 day UTC window. Aggregation is performed in the database and scoped to the active organization; only daily counts are returned. Feedback is a user-reported usefulness signal, not a correctness metric. See `docs/rag-feedback-trends-phase-83.md`.

## Feedback period comparison

The operator API compares two adjacent complete UTC periods of 7–90 days and returns tenant-scoped helpful/unhelpful counts, total volume, absolute and relative count changes, and helpful-rate percentage-point movement. Relative change is omitted when the previous period has no responses; helpful-rate movement is omitted when either period is empty. The operator workbench presents these aggregates alongside the daily feedback chart. User feedback remains a usefulness signal rather than a correctness label. See `docs/rag-feedback-period-comparison-phase-84.md`.

## Feedback backlog aging

The operator API reports aggregate counts for unresolved feedback (`new` and `triaged`) in four rolling UTC age bands: under 24 hours, 1–7 days, 7–30 days, and over 30 days. The query is tenant-scoped and returns zero-filled buckets without individual feedback fields. The operator workbench presents the status breakdown for triage planning. Backlog age is an operational workload signal, not a retrieval-quality metric. See `docs/rag-feedback-backlog-aging-phase-85.md`.

## Feedback lifecycle analytics

The operator API reports daily UTC counts for feedback submissions and transitions into triaged, resolved, and ignored states from the existing tenant-scoped audit trail. The bounded 7–90 day response is zero-filled and contains aggregate counts only. Counts represent audit actions rather than distinct feedback records. The operator workbench presents the lifecycle totals and daily activity. See `docs/rag-feedback-lifecycle-analytics-phase-86.md`.

## Feedback item lifecycle history

Authorized operators can inspect a tenant-scoped, timestamp-only history for an individual feedback record, including submission and triage/resolution/ignored transitions. The workbench supports status filters and expandable histories. Actor identifiers and raw audit details are excluded; legacy records may have incomplete histories. No new audit writes or schema migration are introduced. See `docs/rag-feedback-item-history-phase-87.md`.

## Feedback queue pagination

The operator API provides bounded pages for one feedback lifecycle status, with tenant-scoped totals, stable ordering, and a `has_more` indicator. The workbench loads 25 items per page and retains status filters and per-item lifecycle history. The legacy feedback-list endpoint remains available for compatibility. See `docs/rag-feedback-queue-pagination-phase-88.md`.

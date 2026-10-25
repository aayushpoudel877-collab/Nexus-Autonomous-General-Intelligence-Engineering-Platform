# Phase 54 — RAG source artifact integrity verification

## Goal

Add a small, provider-neutral integrity check that can detect whether source bytes still match the SHA-256 digest captured at ingestion. This complements Phase 52–53 audit retry/idempotency work: idempotent audit delivery prevents duplicate events, while source verification detects changed or unavailable bytes.

## Contract

- Input is a trusted artifact identifier, expected SHA-256 hex digest, and bytes supplied by the storage adapter.
- Results are privacy-safe receipts with identifiers, digests, byte counts, a status, and a bounded reason code. Source content is never copied into the receipt.
- Status values are `verified`, `mismatch`, `unavailable`, and `not_checked`.
- A mismatch is evidence of changed bytes, not proof of malicious tampering. It must be surfaced for investigation and must not automatically mutate document lifecycle state.
- Batch checks are bounded to 500 artifacts by default; individual source payloads are bounded to 25 MiB by default.
- The utility performs no network, database, file-system, or model-provider operations. The caller owns retrieval, tenant authorization, persistence, alerting, and scheduling.

## Validation

The test suite covers matching and changed content, missing bytes, size limits, invalid digests and identifiers, batch order, and malformed/oversized batches.

Run:

```bash
pytest tests/test_rag_source_integrity.py
ruff check services/rag/source_integrity.py tests/test_rag_source_integrity.py
```

## Explicit non-claims / follow-up

This phase is a reusable verification primitive, not a deployed periodic integrity worker. It does not prove the expected digest itself is trustworthy, verify signatures, schedule scans, persist audit events, inspect vector indexes, or provide tamper-proof storage. Production integration should source the expected digest from the trusted ingestion manifest, persist only privacy-safe receipts, and add a scheduled bounded sweep with tenant-aware authorization and operator-reviewed failure handling.

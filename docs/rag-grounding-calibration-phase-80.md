# Phase 80 — Bounded offline review-receipt verification

## Goal

Keep offline receipt verification within the same review-count resource budget as live GitHub review ingestion.

## Changes

- Apply the existing 10,000-review ceiling to the number of serialized review decisions accepted by the receipt verifier.
- Apply the same ceiling to the receipt's aggregate `review_count`, including reviews that do not appear in the final per-reviewer decision list.
- Reject over-limit receipts before iterating through individual decisions or recomputing the receipt digest.
- Preserve the existing versioned schema, canonical SHA-256 integrity check, 1 MB CLI input cap, and compact verification output.
- Add regression tests for both over-limit fields and the exact accepted boundary.

## Security boundaries

The limit is a resource-control measure, not proof that a receipt came from GitHub. SHA-256 detects content changes only when the expected digest is independently trusted; it is not a digital signature. Offline verification does not refresh current GitHub review state or authenticate reviewer identity.

## Validation

The full CI workflow is the acceptance gate: Python lint/tests, web production build, PostgreSQL migration/idempotency checks, and container builds.

# Phase 76 — Deterministic trusted review evidence receipts

## Goal

Make each governed calibration release decision auditable by recording a compact, deterministic receipt of the latest trusted GitHub review state used to authorize it.

## Changes

- Require every GitHub review record to contain a positive integer review ID.
- Reject duplicate review IDs across fetched pages, detecting repeated records caused by inconsistent pagination.
- Resolve equal `submitted_at` timestamps deterministically using the larger GitHub review ID.
- Normalize trusted review timestamps to UTC in the evidence receipt.
- Record the latest state for every allowlisted reviewer on the attested head, including non-approving states such as dismissal or changes requested.
- Include the GitHub review count and a canonical SHA-256 digest over the review receipt in the governed release decision.

## Receipt contents

The digest covers provider, repository, pull-request number, attested head SHA, required approval count, approval-record reviewer, and the sorted latest review decisions. Each decision records reviewer login, GitHub review ID, state, UTC submission time, and attested head SHA. Untrusted reviewers are excluded from the receipt's decision list, but their records remain included in the total review count and pagination integrity checks.

## Security and compatibility

- Existing allowlist, merged-PR, exact-head, active-approval-ledger, provenance, and calibration-regression checks remain mandatory.
- Duplicate IDs and malformed IDs fail closed.
- Review ID is used only as a deterministic tie-break when GitHub timestamps are equal; it does not replace timestamp ordering.
- The digest is an integrity checksum, not a GitHub signature or proof of reviewer identity.
- The receipt contains reviewer logins and is intended for the existing protected release-decision artifact.

## Validation

Phase 75 was merged after all four CI jobs passed: Python lint/tests, web production build, PostgreSQL migration/idempotency checks, and container builds.

Phase 76 must pass the full CI workflow before merge. Local test execution is not claimed.

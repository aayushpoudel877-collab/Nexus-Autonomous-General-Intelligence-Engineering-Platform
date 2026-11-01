# Phase 75 — Bounded trusted GitHub review ingestion

## Goal

Keep trusted-review release verification fail-closed while placing explicit resource bounds on the GitHub API data it consumes.

## Changes

- Limit each GitHub API response body to 1,000,000 bytes. The reader requests at most one byte beyond the configured limit so oversized chunked responses are detected without buffering the complete body.
- Reject a declared `Content-Length` above the limit before reading the response.
- Limit the accumulated review collection to 10,000 entries across all pages.
- Keep the existing 100-page pagination ceiling as a separate request-count bound.
- Add regression tests for oversized declared bodies, oversized streamed bodies, and aggregate review-count overflow.

## Validation

The Phase 74 base revision passed the repository CI workflow, including Ruff, the complete Python test suite, the Next.js production build, PostgreSQL migration downgrade/rebuild and idempotency/concurrency checks, and all three container image builds.

Phase 75 CI must pass on this branch before merge. No local test execution is claimed for this change.

## Security and compatibility notes

- These limits apply only to trusted GitHub review evidence retrieval; they do not change approval semantics, reviewer allowlists, attestation validation, or lifecycle-ledger behavior.
- An oversized or malformed API response causes verification to fail closed.
- The 1 MB response limit and 10,000-review aggregate limit are intentionally conservative operational defaults. If a legitimate repository exceeds them, adjust the constants only with corresponding tests and an explicit resource-budget review.

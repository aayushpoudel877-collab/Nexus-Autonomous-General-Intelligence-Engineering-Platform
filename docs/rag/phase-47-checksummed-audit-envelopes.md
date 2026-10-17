# Phase 47 — Checksummed Provenance Audit Envelopes

## Goal

Make the metadata-only tool-provenance audit payload deterministic and detect accidental or unauthorized edits between creation and verification.

## Implemented

- Add a versioned envelope seal containing a SHA-256 digest over canonical JSON.
- Use deterministic key ordering, compact JSON encoding, UTF-8, and constant-time digest comparison.
- Validate every output against an exact metadata-only schema before sealing or verification.
- Reject raw-output fields, unsupported marker values, invalid identifiers/digests, trust downgrades, boolean-as-integer counts, unsupported schema versions, extra envelope keys, and batches larger than 12.
- Add regression tests for determinism, valid verification, metadata tampering, privacy boundaries, and invalid payloads.

## Security boundaries

The digest is an integrity checksum, not a digital signature. Anyone who can replace both the envelope and its digest can recompute it. Verification must compare against a separately trusted stored digest or rely on an authenticated, append-only audit store. This helper does not persist events, authenticate callers, establish tenant scope, or provide non-repudiation.

## Remaining acceptance work

- Integrate sealing and verification at the actual agentic-tool execution boundary.
- Persist the event and digest in a database transaction with organization-scoped authorization.
- Add real database integration tests for atomic writes, tenant isolation, retention, and deletion.
- Perform human-reviewed security testing before calling the audit path production-ready.

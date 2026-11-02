# Phase 77 — Versioned and independently verified review receipts

## Goal

Make the deterministic GitHub review evidence from Phase 76 independently verifiable at the governed-release boundary, before the evidence is embedded in a release decision.

## Changes

- Add an explicit receipt schema version (schema_version: 1) and include it in the canonical SHA-256 digest.
- Add a strict verifier that rejects missing or unknown top-level and per-decision fields.
- Validate repository and pull-request identifiers, full source revision SHA, reviewer identity, approval threshold, decision states, unique review IDs, sorted unique reviewer decisions, and UTC-normalized timestamps.
- Recompute the canonical receipt digest and compare it using constant-time digest comparison.
- Reconcile the approved-reviewer summary with the individual decision records and enforce the declared approval threshold.
- Invoke receipt verification inside evaluate_governed_release, so malformed or tampered evidence fails closed before a release decision is returned.
- Add focused tests for valid receipts, missing/extra fields, duplicate IDs, timestamp and head mismatches, inconsistent approval summaries, malformed digests, content tampering, and release-boundary enforcement.

## Security boundaries

- The receipt digest detects content changes relative to the digest; it is not a signature and does not authenticate a GitHub account or prove a human's identity.
- The receipt remains dependent on authenticated GitHub API retrieval and the configured trusted-reviewer allowlist.
- Strict schema versioning intentionally rejects unknown fields; a future receipt format must introduce an explicit schema-version migration.
- The release gate still evaluates calibration regression policy separately. A verified review receipt does not make a failing calibration report pass.

## Validation

Phase 77 must pass the full repository CI workflow before merge. The workflow covers Python lint/tests, web production build, PostgreSQL migration/idempotency checks, and container builds. No local test execution is claimed.

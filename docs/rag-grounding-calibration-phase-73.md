# Phase 73 — Calibration approval lifecycle

Phase 73 adds an append-only, hash-chained lifecycle ledger for approval records. It makes approval history reviewable and gives operators explicit revocation and supersession events without rewriting prior events.

## Lifecycle model

- `approved`: records that an approval-record SHA-256 digest was accepted into the ledger.
- `revoked`: retires an active approval digest.
- `superseded`: retires an active approval and activates a distinct replacement approval digest.
- Every event carries a contiguous sequence number, actor identifier, reason, timezone-aware timestamp, previous-event digest, and its own canonical SHA-256 digest.
- Validation replays every transition and rejects broken chains, reordered events, duplicate/replayed approvals, invalid transitions, malformed timestamps, and modified event contents.

## CLI

Append the first approval event (the ledger is initialized if the input path does not yet exist):

```bash
python -m services.rag.calibration_approval_ledger_cli append \
  --ledger calibration-approval-ledger.json \
  --output calibration-approval-ledger.json \
  --action approved \
  --approval-sha256 <approval-record-sha256> \
  --actor-id reviewer-handle \
  --reason "Reviewed baseline and provenance evidence" \
  --occurred-at "2026-10-30T10:00:00Z"
```

Revoke an active approval with `--action revoked`, or supersede it with `--action superseded` and `--replacement-approval-sha256 <new-approval-record-sha256>`. Both actions require the currently active approval digest, actor identifier, reason, and timezone-aware timestamp.

Verify the complete chain and inspect active approval digests:

```bash
python -m services.rag.calibration_approval_ledger_cli verify \
  --ledger calibration-approval-ledger.json
```

The CLI writes updated ledgers atomically. Keep the ledger in access-controlled, append-only or immutable artifact storage and retain it with the corresponding manifest, provenance attestation, approval record, and release decision.

## Trust boundaries

- Actor identifiers and timestamps remain caller-asserted. The ledger does not authenticate users, validate GitHub review permissions, or create digital signatures.
- A hash chain detects edits to retained history, but cannot prevent an attacker with write access from replacing the entire ledger and recomputing every digest. Use protected storage, repository review, and independently retained artifacts.
- The ledger stores approval-record digests; it does not replace validation of the approval record, manifest, provenance attestation, or exact source input bytes.
- A ledger entry is an audit event, not evidence that the underlying baseline is semantically correct or safe for production.
- The CI baseline check remains conditional until a genuinely reviewed baseline and its associated approval evidence are deliberately configured. No baseline or approval is fabricated by this phase.

## Test coverage

Tests cover approval activation, revocation, supersession, duplicate and invalid transitions, replay prevention, tampered event contents, broken links, non-contiguous sequence numbers, timezone requirements, schema validation, and CLI behavior.

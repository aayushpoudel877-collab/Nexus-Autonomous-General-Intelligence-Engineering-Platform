# Phase 78 — Offline review-receipt verification CLI

## Goal

Make Phase 77's versioned GitHub review receipt independently verifiable from a saved JSON artifact, without requiring a GitHub token or a live API call.

## Changes

- Add `services.rag.calibration_review_receipt_cli` with a `--receipt` input.
- Reuse the Phase 77 strict schema, policy-consistency, and canonical digest verifier rather than maintaining a second implementation.
- Bound receipt input to 1,000,000 bytes before decoding or parsing.
- Reject malformed UTF-8, malformed JSON, non-finite JSON constants, and non-object top-level values.
- Emit a compact machine-readable summary and a non-zero exit code for invalid evidence.
- Avoid printing the full review decision list or other unnecessary receipt contents.
- Add CLI and input-contract regression tests.

## Usage

```bash
python -m services.rag.calibration_review_receipt_cli --receipt review-receipt.json
```

Exit status is `0` only when the receipt passes the Phase 77 verifier; invalid or unreadable evidence returns `2`.

## Security boundaries

- The SHA-256 digest is an integrity check, not a digital signature or proof of reviewer identity.
- Offline verification confirms internal receipt consistency only. It does not contact GitHub, prove that the receipt was genuinely issued by GitHub, or refresh approval status.
- Use the governed-release evaluator for a live authenticated GitHub review check.
- Receipt files are treated as untrusted input and are size-bounded before parsing.

## Validation

The full repository CI workflow is the merge gate: Python lint/tests, web production build, PostgreSQL migration/idempotency checks, and container builds. No local execution is claimed.

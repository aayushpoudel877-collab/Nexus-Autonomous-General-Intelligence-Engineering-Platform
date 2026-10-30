# Phase 72 — Calibration approval governance

Phase 72 introduces a review record that binds an approved calibration baseline manifest to its exact provenance attestation. It does not manufacture approval or establish that a reviewer identity is authentic.

## Review workflow

1. Generate the calibration report using the repository evaluator.
2. Create a provenance attestation for the report and every material input file (Phase 71).
3. Create a versioned baseline manifest from the reviewed report (Phase 68).
4. Inspect the report, manifest, dataset, evaluator, and limitations.
5. After an actual review, record the reviewer identifier, reason, and timezone-aware review time:

```bash
python -m services.rag.calibration_approval_cli create \
  --manifest approved-baseline.json \
  --attestation calibration.provenance.json \
  --input grounding-dataset=tests/fixtures/rag/grounding.jsonl \
  --reviewer-id reviewer-handle \
  --review-reason "Reviewed dataset labels, evaluator, report, and known limitations" \
  --reviewed-at "2026-10-30T09:00:00Z" \
  --output calibration.approval.json
```

The command validates the manifest, checks that the attestation is for the exact embedded report, and verifies the exact bytes of all attested input files before writing the approval record atomically.

## Verify an approval

```bash
python -m services.rag.calibration_approval_cli verify \
  --manifest approved-baseline.json \
  --attestation calibration.provenance.json \
  --approval calibration.approval.json \
  --input grounding-dataset=tests/fixtures/rag/grounding.jsonl
```

Verification checks the approval-record digest, manifest digest, attestation digest, report binding, reviewer/reason fields, timezone-aware timestamp, and input-file hashes. Supply every input label recorded in the attestation; missing or additional labels fail verification.

## Trust and security boundaries

- The reviewer identifier and review timestamp are caller-supplied assertions. This CLI does not authenticate users, check repository permissions, or establish that a person actually performed the review.
- The digest detects accidental or unsophisticated modification; it is not a digital signature. Protect approval artifacts with trusted code review, access controls, and immutable CI/audit storage.
- An approval record is separate from the release-gate decision. The release gate still evaluates the current report against the approved manifest and configured regression policy.
- Approval does not prove semantic entailment, factual correctness, representative benchmark coverage, or production safety.
- Never create an approval record automatically from the same candidate run being assessed. Human review must precede approval.

See Phase 68 for baseline manifests, Phase 69 for release gates, Phase 70 for case-set drift policy, and Phase 71 for provenance attestations.

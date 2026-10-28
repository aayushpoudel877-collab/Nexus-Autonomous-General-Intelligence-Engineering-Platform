# Phase 68 — Approved calibration baselines and release governance

Phase 68 adds content-addressed baseline manifests for grounding calibration.
A manifest embeds the complete report, its SHA-256 fingerprint, a fingerprint of
the sorted case-ID set when available, a monotonically increasing baseline
version, and a human-readable approval reason. The manifest is deterministic:
it deliberately omits a generated timestamp so equivalent approvals are
byte-for-byte reproducible after JSON formatting.

## Generate and approve a baseline

First create a report using the existing fixture evaluator:

```bash
python -m services.rag.grounding_calibration_cli --output calibration-report.json
python -m services.rag.calibration_baseline_cli approve \
  --report calibration-report.json \
  --output tests/fixtures/rag/grounding-calibration-baseline.json \
  --version 1 \
  --reason "Reviewed offline grounding calibration baseline"
```

Review the report and the approval reason before committing the manifest. The
CLI does not update a baseline automatically during tests or CI.

## Verify and compare against an approved baseline

```bash
python -m services.rag.calibration_baseline_cli verify \
  --manifest tests/fixtures/rag/grounding-calibration-baseline.json

python -m services.rag.calibration_report_diff_cli \
  --baseline-manifest tests/fixtures/rag/grounding-calibration-baseline.json \
  --current calibration-report.json
```

The comparison report records the baseline version and both integrity
fingerprints alongside the existing regression deltas. Legacy raw JSON
baselines remain supported with `--baseline`.

## Updating a baseline safely

Replacing an existing manifest requires the current report fingerprint and a
strictly greater version:

```bash
python -m services.rag.calibration_baseline_cli approve \
  --report calibration-report.json \
  --output tests/fixtures/rag/grounding-calibration-baseline.json \
  --version 2 \
  --reason "Approved after reviewed fixture and verifier update" \
  --expected-current-report-sha CURRENT_REPORT_SHA256
```

This optimistic-concurrency guard prevents an update based on a stale manifest.
Writes use a temporary file followed by an atomic replacement. Invalid reports,
tampered hashes, missing approval reasons, stale hashes, and non-increasing
versions fail without silently replacing the existing baseline.

## Scope and limitations

SHA-256 detects accidental or unreviewed content changes when the expected
manifest is trusted; it is not a digital signature and does not prove who
approved a baseline. Protect review and branch permissions, and review the
manifest diff like code. Fixture metrics indicate agreement with expected
labels, not semantic entailment, factual correctness, or production safety.

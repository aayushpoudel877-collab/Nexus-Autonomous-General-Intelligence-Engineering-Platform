# Phase 71 — Grounding calibration provenance attestations

Phase 71 adds a deterministic sidecar that binds an offline grounding calibration report to the exact input-file bytes, the source revision, and the evaluator identity.

## Create an attestation

Generate the report with the existing evaluator first. Then attest that report and every file that materially contributed to it:

```bash
python -m services.rag.calibration_provenance_cli create \
  --report grounding-calibration-current.json \
  --input grounding-dataset=tests/fixtures/rag/grounding.jsonl \
  --source-revision "$(git rev-parse HEAD)" \
  --evaluator "python -m services.rag.grounding_calibration_cli" \
  --output grounding-calibration-current.provenance.json
```

Repeat `--input LABEL=PATH` for each relevant source file. Labels must be unique. The sidecar stores SHA-256 and byte length for each input, the report SHA-256, source revision, and evaluator identifier. It does not copy source data into the attestation.

## Verify later

```bash
python -m services.rag.calibration_provenance_cli verify \
  --report grounding-calibration-current.json \
  --attestation grounding-calibration-current.provenance.json \
  --input grounding-dataset=tests/fixtures/rag/grounding.jsonl
```

Verification fails if the report changes, an input label is missing/extra, or any input bytes differ. Keep the report, attestation, and reviewed source inputs together as a CI artifact or review attachment.

## Approval boundary

An attestation is provenance evidence, not an approval and not proof that labels are correct. A reviewer must still inspect the dataset, evaluator, report, and proposed baseline changes. Do not generate a baseline from the same candidate run being evaluated and treat that as independent approval. The existing versioned baseline CLI remains the explicit approval mechanism.

The attestation records a caller-supplied revision and evaluator string; it does not independently query Git, prove the command was executed, establish reviewer identity, or provide a cryptographic signature. Store it alongside trusted CI logs and code review records. Calibration results remain fixture agreement signals, not semantic entailment or production-safety guarantees.

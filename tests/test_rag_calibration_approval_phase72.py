from __future__ import annotations

import json
import subprocess
import sys

import pytest

from services.rag.calibration_approval import (
    build_approval_record,
    validate_approval_record,
)
from services.rag.calibration_baseline import build_manifest
from services.rag.calibration_provenance import build_attestation

CLI = [sys.executable, "-m", "services.rag.calibration_approval_cli"]


def _report() -> dict:
    return {
        "schema_version": 1,
        "case_count": 1,
        "accuracy": 1.0,
        "macro_f1": 1.0,
        "breakdown": {},
        "status_metrics": {},
        "case_results": [
            {
                "case_id": "reviewed-case",
                "expected": "grounded",
                "actual": "grounded",
                "passed": True,
            }
        ],
    }


def _evidence(tmp_path):
    source = tmp_path / "dataset.jsonl"
    source.write_text('{"case_id":"reviewed-case"}\n', encoding="utf-8")
    report = _report()
    manifest = build_manifest(report, version=1, reason="Reviewed calibration candidate")
    attestation = build_attestation(
        report,
        inputs={"dataset": source},
        source_revision="a" * 40,
        evaluator="offline-grounding-evaluator",
    )
    return manifest, attestation, source


def test_approval_record_binds_manifest_attestation_and_reviewer(tmp_path):
    manifest, attestation, _ = _evidence(tmp_path)
    record = build_approval_record(
        manifest,
        attestation,
        reviewer_id="reviewer-17",
        review_reason="Reviewed labels, evaluator output, and known limitations",
        reviewed_at="2026-10-30T09:00:00Z",
    )

    assert validate_approval_record(record, manifest, attestation) == record
    assert record["baseline_version"] == 1
    assert record["source_revision"] == "a" * 40


def test_approval_rejects_attestation_for_different_report(tmp_path):
    manifest, attestation, source = _evidence(tmp_path)
    altered_report = _report()
    altered_report["accuracy"] = 0.5
    unrelated = build_attestation(
        altered_report,
        inputs={"dataset": source},
        source_revision="b" * 40,
        evaluator="offline-grounding-evaluator",
    )
    with pytest.raises(ValueError, match="report SHA-256"):
        build_approval_record(
            manifest,
            unrelated,
            reviewer_id="reviewer",
            review_reason="reviewed",
            reviewed_at="2026-10-30T09:00:00Z",
        )


def test_approval_record_detects_tampering_and_manifest_substitution(tmp_path):
    manifest, attestation, _ = _evidence(tmp_path)
    record = build_approval_record(
        manifest,
        attestation,
        reviewer_id="reviewer",
        review_reason="reviewed",
        reviewed_at="2026-10-30T09:00:00+00:00",
    )
    tampered = dict(record, review_reason="changed after approval")
    with pytest.raises(ValueError, match="SHA-256"):
        validate_approval_record(tampered, manifest, attestation)

    other_manifest = build_manifest(
        {**_report(), "accuracy": 0.75},
        version=2,
        reason="different baseline",
    )
    with pytest.raises(ValueError, match="does not match"):
        validate_approval_record(record, other_manifest, attestation)


@pytest.mark.parametrize(
    ("reviewer", "reason", "timestamp"),
    [
        ("", "reviewed", "2026-10-30T09:00:00Z"),
        ("reviewer", " ", "2026-10-30T09:00:00Z"),
        ("reviewer", "reviewed", "2026-10-30T09:00:00"),
    ],
)
def test_approval_requires_reviewer_reason_and_timezone(reviewer, reason, timestamp, tmp_path):
    manifest, attestation, _ = _evidence(tmp_path)
    with pytest.raises(ValueError):
        build_approval_record(
            manifest,
            attestation,
            reviewer_id=reviewer,
            review_reason=reason,
            reviewed_at=timestamp,
        )


def test_approval_cli_create_and_verify(tmp_path):
    manifest, attestation, source = _evidence(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    attestation_path = tmp_path / "attestation.json"
    approval_path = tmp_path / "approval.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    attestation_path.write_text(json.dumps(attestation), encoding="utf-8")

    created = subprocess.run(
        CLI + [
            "create", "--manifest", str(manifest_path),
            "--attestation", str(attestation_path),
            "--reviewer-id", "reviewer-17",
            "--review-reason", "Reviewed candidate evidence",
            "--reviewed-at", "2026-10-30T09:00:00Z",
            "--output", str(approval_path), "--input", f"dataset={source}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    verified = subprocess.run(
        CLI + [
            "verify", "--manifest", str(manifest_path),
            "--attestation", str(attestation_path),
            "--approval", str(approval_path), "--input", f"dataset={source}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert created.returncode == 0, created.stderr
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["valid"] is True


def test_approval_cli_rejects_changed_attestation(tmp_path):
    manifest, attestation, _ = _evidence(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    attestation_path = tmp_path / "attestation.json"
    approval_path = tmp_path / "approval.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    attestation_path.write_text(json.dumps(attestation), encoding="utf-8")
    created = subprocess.run(
        CLI + [
            "create", "--manifest", str(manifest_path),
            "--attestation", str(attestation_path),
            "--reviewer-id", "reviewer",
            "--review-reason", "Reviewed",
            "--reviewed-at", "2026-10-30T09:00:00Z",
            "--output", str(approval_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    attestation["source_revision"] = "tampered"
    attestation_path.write_text(json.dumps(attestation), encoding="utf-8")
    verified = subprocess.run(
        CLI + [
            "verify", "--manifest", str(manifest_path),
            "--attestation", str(attestation_path),
            "--approval", str(approval_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    assert verified.returncode == 2

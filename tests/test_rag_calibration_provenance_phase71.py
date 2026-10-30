from __future__ import annotations

import json
import subprocess
import sys

import pytest

from services.rag.calibration_provenance import (
    build_attestation,
    validate_attestation,
    verify_input_files,
)

CLI = [sys.executable, "-m", "services.rag.calibration_provenance_cli"]


def _report() -> dict:
    return {
        "schema_version": 1, "case_count": 1, "accuracy": 1.0, "macro_f1": 0.25,
        "breakdown": {}, "status_metrics": {},
        "case_results": [
            {"case_id": "case-1", "expected": "grounded", "actual": "grounded", "passed": True}
        ],
    }


def test_attestation_binds_report_revision_evaluator_and_input_bytes(tmp_path):
    dataset = tmp_path / "grounding.jsonl"
    dataset.write_text('{"case_id":"case-1"}\\n', encoding="utf-8")
    attestation = build_attestation(
        _report(), inputs={"grounding-dataset": dataset},
        source_revision="abc123", evaluator="grounding-calibration-cli",
    )
    assert validate_attestation(attestation, _report()) == attestation
    verify_input_files(attestation, {"grounding-dataset": dataset})
    assert attestation["inputs"]["grounding-dataset"]["size_bytes"] == dataset.stat().st_size


def test_attestation_rejects_changed_report_and_changed_input(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("original\\n", encoding="utf-8")
    attestation = build_attestation(
        _report(), inputs={"dataset": dataset}, source_revision="abc", evaluator="eval"
    )
    changed_report = _report()
    changed_report["accuracy"] = 0.5
    with pytest.raises(ValueError, match="report SHA-256"):
        validate_attestation(attestation, changed_report)
    dataset.write_text("modified\\n", encoding="utf-8")
    with pytest.raises(ValueError, match="input mismatch"):
        verify_input_files(attestation, {"dataset": dataset})


def test_attestation_rejects_missing_or_extra_input_labels(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("data", encoding="utf-8")
    attestation = build_attestation(
        _report(), inputs={"dataset": dataset}, source_revision="abc", evaluator="eval"
    )
    with pytest.raises(ValueError, match="labels"):
        verify_input_files(attestation, {"other": dataset})


def test_cli_create_and_verify_round_trip(tmp_path):
    report = tmp_path / "report.json"
    dataset = tmp_path / "dataset.jsonl"
    attestation = tmp_path / "attestation.json"
    report.write_text(json.dumps(_report()), encoding="utf-8")
    dataset.write_text("reviewed inputs\\n", encoding="utf-8")
    created = subprocess.run(
        CLI + ["create", "--report", str(report), "--input", f"dataset={dataset}",
               "--source-revision", "abc123", "--evaluator", "offline-evaluator",
               "--output", str(attestation)],
        capture_output=True, text=True, check=False,
    )
    verified = subprocess.run(
        CLI + ["verify", "--report", str(report), "--attestation", str(attestation),
               "--input", f"dataset={dataset}"],
        capture_output=True, text=True, check=False,
    )
    assert created.returncode == 0, created.stderr
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["valid"] is True


def test_cli_fails_when_input_bytes_change(tmp_path):
    report = tmp_path / "report.json"
    dataset = tmp_path / "dataset.jsonl"
    attestation = tmp_path / "attestation.json"
    report.write_text(json.dumps(_report()), encoding="utf-8")
    dataset.write_text("before", encoding="utf-8")
    create = subprocess.run(
        CLI + ["create", "--report", str(report), "--input", f"dataset={dataset}",
               "--source-revision", "abc123", "--evaluator", "offline-evaluator",
               "--output", str(attestation)],
        capture_output=True, text=True, check=False,
    )
    dataset.write_text("after", encoding="utf-8")
    verify = subprocess.run(
        CLI + ["verify", "--report", str(report), "--attestation", str(attestation),
               "--input", f"dataset={dataset}"],
        capture_output=True, text=True, check=False,
    )
    assert create.returncode == 0, create.stderr
    assert verify.returncode == 2
    assert "input mismatch" in verify.stderr


@pytest.mark.parametrize(("revision", "evaluator"), [("", "eval"), ("abc", "  ")])
def test_attestation_requires_revision_and_evaluator(tmp_path, revision, evaluator):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("data", encoding="utf-8")
    with pytest.raises(ValueError):
        build_attestation(
            _report(), inputs={"dataset": dataset},
            source_revision=revision, evaluator=evaluator,
        )


def test_attestation_rejects_boolean_schema_version(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("data", encoding="utf-8")
    attestation = build_attestation(
        _report(), inputs={"dataset": dataset}, source_revision="abc", evaluator="eval"
    )
    attestation["schema_version"] = True
    with pytest.raises(ValueError, match="schema_version"):
        validate_attestation(attestation, _report())


def test_attestation_rejects_malformed_input_digest(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("data", encoding="utf-8")
    attestation = build_attestation(
        _report(), inputs={"dataset": dataset}, source_revision="abc", evaluator="eval"
    )
    attestation["inputs"]["dataset"]["sha256"] = "not-a-digest"
    with pytest.raises(ValueError, match="invalid SHA-256"):
        validate_attestation(attestation, _report())

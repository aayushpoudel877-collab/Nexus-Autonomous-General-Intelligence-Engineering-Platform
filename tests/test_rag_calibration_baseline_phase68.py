from __future__ import annotations

import json
import subprocess
import sys

import pytest

from services.rag.calibration_baseline import (
    build_manifest,
    load_manifest,
    sha256_json,
    validate_manifest,
)

CLI = [sys.executable, "-m", "services.rag.calibration_baseline_cli"]


def _report() -> dict:
    return {
        "schema_version": 1,
        "case_count": 2,
        "passed": 2,
        "failed": 0,
        "accuracy": 1.0,
        "macro_f1": 0.25,
        "confusion": {"grounded->grounded": 2},
        "status_metrics": {
            "grounded": {"support": 2, "precision": 1.0, "recall": 1.0, "f1": 1.0},
            "unsupported": {"support": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0},
            "contradictory": {"support": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0},
            "inconclusive": {"support": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0},
        },
        "breakdown": {"category": {"security": {"case_count": 2, "accuracy": 1.0}}},
        "case_results": [
            {"case_id": "a", "expected": "grounded", "actual": "grounded", "passed": True},
            {"case_id": "b", "expected": "grounded", "actual": "grounded", "passed": True},
        ],
    }


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(CLI + list(args), capture_output=True, text=True, check=False)


def test_manifest_is_deterministic_and_binds_report_and_case_set():
    report = _report()
    first = build_manifest(report, version=1, reason="reviewed fixture update")
    second = build_manifest(report, version=1, reason="reviewed fixture update")

    assert first == second
    assert first["report_sha256"] == sha256_json(report)
    assert first["case_set_sha256"] == sha256_json(["a", "b"])
    assert validate_manifest(first) == first


def test_manifest_detects_report_tampering():
    manifest = build_manifest(_report(), version=1, reason="approved baseline")
    manifest["report"]["accuracy"] = 0.5

    with pytest.raises(ValueError, match="report SHA-256"):
        validate_manifest(manifest)


def test_manifest_detects_case_set_tampering():
    manifest = build_manifest(_report(), version=1, reason="approved baseline")
    manifest["case_set_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="case-set SHA-256"):
        validate_manifest(manifest)


@pytest.mark.parametrize(
    ("version", "reason", "message"),
    [
        (0, "valid reason", "positive integer"),
        (True, "valid reason", "positive integer"),
        (1, "   ", "non-empty string"),
    ],
)
def test_manifest_approval_requires_valid_version_and_reason(version, reason, message):
    with pytest.raises(ValueError, match=message):
        build_manifest(_report(), version=version, reason=reason)


def test_manifest_without_case_results_is_supported():
    report = _report()
    report.pop("case_results")
    manifest = build_manifest(report, version=1, reason="legacy report")

    assert manifest["case_set_sha256"] is None
    assert validate_manifest(manifest)["report"] == report


def test_cli_approve_and_verify_round_trip(tmp_path):
    report_path = tmp_path / "report.json"
    manifest_path = tmp_path / "approved" / "baseline.json"
    report_path.write_text(json.dumps(_report()), encoding="utf-8")

    approved = _run(
        "approve", "--report", str(report_path), "--output", str(manifest_path),
        "--version", "1", "--reason", "Phase 68 reviewed baseline",
    )
    verified = _run("verify", "--manifest", str(manifest_path))

    assert approved.returncode == 0, approved.stderr
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["valid"] is True
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["baseline_version"] == 1


def test_cli_refuses_overwrite_without_expected_current_report_hash(tmp_path):
    report_path = tmp_path / "report.json"
    manifest_path = tmp_path / "baseline.json"
    report_path.write_text(json.dumps(_report()), encoding="utf-8")
    args = (
        "approve", "--report", str(report_path), "--output", str(manifest_path),
        "--version", "1", "--reason", "initial approval",
    )
    assert _run(*args).returncode == 0

    result = _run(
        "approve", "--report", str(report_path), "--output", str(manifest_path),
        "--version", "2", "--reason", "new approval",
    )

    assert result.returncode == 2
    assert "supply --expected-current-report-sha" in result.stderr


def test_cli_requires_matching_previous_hash_and_increasing_version(tmp_path):
    report_path = tmp_path / "report.json"
    manifest_path = tmp_path / "baseline.json"
    report_path.write_text(json.dumps(_report()), encoding="utf-8")
    assert _run(
        "approve", "--report", str(report_path), "--output", str(manifest_path),
        "--version", "1", "--reason", "initial approval",
    ).returncode == 0
    old = load_manifest(manifest_path)

    stale = _run(
        "approve", "--report", str(report_path), "--output", str(manifest_path),
        "--version", "2", "--reason", "new approval",
        "--expected-current-report-sha", "0" * 64,
    )
    same_version = _run(
        "approve", "--report", str(report_path), "--output", str(manifest_path),
        "--version", "1", "--reason", "same version",
        "--expected-current-report-sha", old["report_sha256"],
    )
    replacement = _run(
        "approve", "--report", str(report_path), "--output", str(manifest_path),
        "--version", "2", "--reason", "reviewed replacement",
        "--expected-current-report-sha", old["report_sha256"],
    )

    assert stale.returncode == 2
    assert "does not match" in stale.stderr
    assert same_version.returncode == 2
    assert "must be greater" in same_version.stderr
    assert replacement.returncode == 0, replacement.stderr
    assert load_manifest(manifest_path)["baseline_version"] == 2


def test_report_diff_cli_accepts_manifest_as_baseline(tmp_path):
    report_path = tmp_path / "report.json"
    manifest_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    report_path.write_text(json.dumps(_report()), encoding="utf-8")
    current = _report()
    current["case_results"][0]["case_id"] = "a"
    current_path.write_text(json.dumps(current), encoding="utf-8")
    assert _run(
        "approve", "--report", str(report_path), "--output", str(manifest_path),
        "--version", "3", "--reason", "CI-reviewed baseline",
    ).returncode == 0

    result = subprocess.run(
        [
            sys.executable, "-m", "services.rag.calibration_report_diff_cli",
            "--baseline-manifest", str(manifest_path), "--current", str(current_path),
        ],
        capture_output=True, text=True, check=False,
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["baseline"]["version"] == 3
    assert output["baseline"]["report_sha256"]


def test_cli_rejects_malformed_report_without_writing_manifest(tmp_path):
    report_path = tmp_path / "bad.json"
    manifest_path = tmp_path / "baseline.json"
    report_path.write_text("{", encoding="utf-8")

    result = _run(
        "approve", "--report", str(report_path), "--output", str(manifest_path),
        "--version", "1", "--reason", "test",
    )

    assert result.returncode == 2
    assert not manifest_path.exists()



def test_manifest_rejects_boolean_schema_version():
    manifest = build_manifest(_report(), version=1, reason="approved")
    manifest["manifest_schema_version"] = True

    with pytest.raises(ValueError, match="unsupported baseline manifest schema version"):
        validate_manifest(manifest)

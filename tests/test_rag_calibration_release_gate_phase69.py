from __future__ import annotations

import json
import subprocess
import sys

from services.rag.calibration_baseline import build_manifest
from services.rag.calibration_release_gate import evaluate_release_gate

CLI = [sys.executable, "-m", "services.rag.calibration_release_gate_cli"]


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


def _manifest(report: dict | None = None) -> dict:
    return build_manifest(report or _report(), version=4, reason="reviewed release baseline")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(CLI + list(args), capture_output=True, text=True, check=False)


def test_release_gate_passes_and_is_deterministic():
    baseline = _manifest()
    first = evaluate_release_gate(baseline, _report())
    second = evaluate_release_gate(baseline, _report())

    assert first == second
    assert first["decision"] == "pass"
    assert first["baseline"]["version"] == 4
    assert first["current"]["report_sha256"]
    assert first["regressions"] == []


def test_release_gate_fails_on_accuracy_drop_and_new_case_failure():
    baseline = _report()
    current = _report()
    current["accuracy"] = 0.5
    current["passed"] = 1
    current["failed"] = 1
    current["case_results"][1]["actual"] = "unsupported"
    current["case_results"][1]["passed"] = False
    current["breakdown"]["category"]["security"]["accuracy"] = 0.5

    result = evaluate_release_gate(_manifest(baseline), current)

    assert result["decision"] == "fail"
    assert any("accuracy dropped" in item for item in result["regressions"])
    assert "case newly failing: b" in result["regressions"]


def test_release_gate_can_allow_new_case_failures_when_explicitly_configured():
    baseline = _report()
    current = _report()
    current["case_results"][1]["actual"] = "unsupported"
    current["case_results"][1]["passed"] = False

    result = evaluate_release_gate(
        _manifest(baseline), current, fail_on_new_case_failures=False
    )

    assert result["decision"] == "pass"
    assert result["regressions"] == []


def test_release_gate_rejects_tampered_manifest():
    manifest = _manifest()
    manifest["report"]["accuracy"] = 0.1

    try:
        evaluate_release_gate(manifest, _report())
    except ValueError as exc:
        assert "SHA-256" in str(exc)
    else:
        raise AssertionError("tampered baseline must be rejected")


def test_cli_writes_fail_decision_artifact_even_when_gate_fails(tmp_path):
    baseline_report = _report()
    current = _report()
    current["accuracy"] = 0.5
    current["case_results"][1]["actual"] = "unsupported"
    current["case_results"][1]["passed"] = False
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    output_path = tmp_path / "artifacts" / "release-decision.json"
    baseline_path.write_text(json.dumps(_manifest(baseline_report)), encoding="utf-8")
    current_path.write_text(json.dumps(current), encoding="utf-8")

    result = _run(
        "--baseline-manifest", str(baseline_path),
        "--current", str(current_path),
        "--output", str(output_path),
    )

    assert result.returncode == 1
    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert artifact["decision"] == "fail"
    assert artifact["baseline"]["version"] == 4
    assert artifact["regressions"]


def test_cli_writes_error_artifact_for_invalid_baseline(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    output_path = tmp_path / "decision.json"
    baseline_path.write_text("{", encoding="utf-8")
    current_path.write_text(json.dumps(_report()), encoding="utf-8")

    result = _run(
        "--baseline-manifest", str(baseline_path),
        "--current", str(current_path),
        "--output", str(output_path),
    )

    assert result.returncode == 2
    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert artifact["decision"] == "error"
    assert "cannot read baseline manifest" in artifact["error"]


def test_cli_passes_and_emits_machine_readable_artifact(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    output_path = tmp_path / "decision.json"
    baseline_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    current_path.write_text(json.dumps(_report()), encoding="utf-8")

    result = _run(
        "--baseline-manifest", str(baseline_path),
        "--current", str(current_path),
        "--output", str(output_path),
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["decision"] == "pass"
    assert json.loads(output_path.read_text(encoding="utf-8"))["decision"] == "pass"


def test_cli_rejects_non_finite_json_and_still_writes_error_artifact(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    output_path = tmp_path / "decision.json"
    baseline_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    current_path.write_text('{"accuracy": NaN}', encoding="utf-8")

    result = _run(
        "--baseline-manifest", str(baseline_path),
        "--current", str(current_path),
        "--output", str(output_path),
    )

    assert result.returncode == 2
    assert json.loads(output_path.read_text(encoding="utf-8"))["decision"] == "error"

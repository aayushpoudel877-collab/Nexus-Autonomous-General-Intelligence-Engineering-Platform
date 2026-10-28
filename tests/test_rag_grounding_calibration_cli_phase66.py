from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

CLI = [sys.executable, "-m", "services.rag.grounding_calibration_cli"]


def _case(directory: Path, case_id: str, expected: str, evidence: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    value = {
        "case_id": case_id,
        "claim": "Nexus supports encrypted storage",
        "citations": ["E1"],
        "evidence": [{"evidence_id": "E1", "text": evidence}],
        "expected_status": expected,
    }
    (directory / f"{case_id}.json").write_text(json.dumps(value), encoding="utf-8")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(CLI + list(args), capture_output=True, text=True, check=False)


def test_cli_report_includes_status_metrics_and_macro_f1(tmp_path):
    fixtures = tmp_path / "fixtures"
    _case(fixtures, "grounded", "grounded", "Nexus supports encrypted storage")

    result = _run("--fixtures", str(fixtures))

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status_metrics"]["grounded"]["f1"] == 1.0
    assert report["macro_f1"] == 0.25


def test_cli_macro_f1_gate_fails_below_threshold(tmp_path):
    fixtures = tmp_path / "fixtures"
    _case(fixtures, "mismatch", "grounded", "Penguins swim in the ocean")

    result = _run("--fixtures", str(fixtures), "--min-macro-f1", "0.5")

    assert result.returncode == 1
    assert "macro F1" in result.stderr
    assert "below minimum" in result.stderr


def test_cli_macro_f1_gate_accepts_zero_threshold(tmp_path):
    fixtures = tmp_path / "fixtures"
    _case(fixtures, "mismatch", "grounded", "Penguins swim in the ocean")

    result = _run("--fixtures", str(fixtures), "--min-macro-f1", "0")

    assert result.returncode == 1
    assert "macro F1" not in result.stderr


def test_cli_rejects_out_of_range_macro_f1_threshold():
    result = _run("--min-macro-f1", "1.1")

    assert result.returncode == 2
    assert "--min-macro-f1 must be between 0 and 1" in result.stderr

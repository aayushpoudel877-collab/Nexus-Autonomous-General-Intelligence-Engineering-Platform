from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

CLI = [sys.executable, "-m", "services.rag.grounding_calibration_cli"]


def _write_case(directory: Path, case_id: str, expected: str, claim: str, evidence: str):
    directory.mkdir(parents=True, exist_ok=True)
    case = {
        "case_id": case_id,
        "claim": claim,
        "citations": ["E1"],
        "evidence": [{"evidence_id": "E1", "text": evidence}],
        "expected_status": expected,
        "category": "test",
        "language": "en",
    }
    (directory / f"{case_id}.json").write_text(
        json.dumps(case, ensure_ascii=False), encoding="utf-8"
    )


def _run(*args):
    return subprocess.run(CLI + list(args), capture_output=True, text=True, check=False)


def test_cli_filters_by_case_prefix(tmp_path):
    fixtures = tmp_path / "fixtures"
    _write_case(fixtures, "selected-one", "grounded", "Nexus stores records", "Nexus stores records")
    _write_case(fixtures, "other-two", "grounded", "Nexus stores records", "Nexus stores records")

    result = _run("--fixtures", str(fixtures), "--case-prefix", "selected-")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["case_count"] == 1


def test_cli_filters_by_category_and_language(tmp_path):
    fixtures = tmp_path / "fixtures"
    _write_case(fixtures, "target-one", "grounded", "Nexus stores records", "Nexus stores records")
    case_path = fixtures / "target-one.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    case["category"] = "security"
    case["language"] = "ne"
    case_path.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")

    result = _run(
        "--fixtures", str(fixtures), "--category", "security", "--language", "ne"
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["case_count"] == 1


def test_cli_filters_by_expected_status(tmp_path):
    fixtures = tmp_path / "fixtures"
    _write_case(fixtures, "grounded-one", "grounded", "Nexus stores records", "Nexus stores records")
    _write_case(fixtures, "unsupported-two", "unsupported", "Nexus stores records", "Penguins swim")

    result = _run("--fixtures", str(fixtures), "--status", "unsupported")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["case_count"] == 1


def test_cli_writes_filtered_report_to_nested_output_path(tmp_path):
    fixtures = tmp_path / "fixtures"
    output = tmp_path / "reports" / "nested" / "report.json"
    _write_case(fixtures, "one", "grounded", "Nexus stores records", "Nexus stores records")

    result = _run("--fixtures", str(fixtures), "--output", str(output))

    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["case_count"] == 1


def test_cli_accuracy_gate_fails_when_threshold_is_not_met(tmp_path):
    fixtures = tmp_path / "fixtures"
    _write_case(fixtures, "mismatch", "grounded", "Nexus stores records", "Penguins swim")

    result = _run("--fixtures", str(fixtures), "--min-accuracy", "1.0")

    assert result.returncode == 1
    assert "below minimum" in result.stderr


def test_cli_accuracy_gate_accepts_zero_threshold(tmp_path):
    fixtures = tmp_path / "fixtures"
    _write_case(
        fixtures, "match", "grounded", "Nexus stores records", "Nexus stores records"
    )

    result = _run("--fixtures", str(fixtures), "--min-accuracy", "0")

    assert result.returncode == 0, result.stderr


def test_cli_rejects_out_of_range_accuracy_threshold():
    result = _run("--min-accuracy", "1.1")

    assert result.returncode == 2
    assert "--min-accuracy must be between 0 and 1" in result.stderr


def test_cli_returns_two_when_filters_match_no_cases(tmp_path):
    fixtures = tmp_path / "fixtures"
    _write_case(fixtures, "one", "grounded", "Nexus stores records", "Nexus stores records")

    result = _run("--fixtures", str(fixtures), "--case-prefix", "missing-")

    assert result.returncode == 2
    assert "selected zero cases" in result.stderr


def test_cli_reports_output_write_errors_with_exit_code_two(tmp_path):
    fixtures = tmp_path / "fixtures"
    _write_case(fixtures, "one", "grounded", "Nexus stores records", "Nexus stores records")
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("file", encoding="utf-8")
    output = blocker / "report.json"

    result = _run("--fixtures", str(fixtures), "--output", str(output))

    assert result.returncode == 2
    assert "failed to write report" in result.stderr


def test_cli_repeated_status_values_use_or_semantics(tmp_path):
    fixtures = tmp_path / "fixtures"
    _write_case(fixtures, "grounded", "grounded", "Nexus stores records", "Nexus stores records")
    _write_case(fixtures, "unsupported", "unsupported", "Nexus stores records", "Penguins swim")

    result = _run(
        "--fixtures", str(fixtures), "--status", "grounded", "--status", "unsupported"
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["case_count"] == 2


def test_cli_different_filters_combine_with_and_semantics(tmp_path):
    fixtures = tmp_path / "fixtures"
    _write_case(fixtures, "security-one", "grounded", "Nexus stores records", "Nexus stores records")
    _write_case(fixtures, "cache-two", "grounded", "Nexus stores records", "Nexus stores records")
    for name, category in (("security-one", "security"), ("cache-two", "cache")):
        path = fixtures / f"{name}.json"
        case = json.loads(path.read_text(encoding="utf-8"))
        case["category"] = category
        path.write_text(json.dumps(case), encoding="utf-8")

    result = _run(
        "--fixtures", str(fixtures), "--category", "security", "--case-prefix", "cache-"
    )

    assert result.returncode == 2
    assert "selected zero cases" in result.stderr

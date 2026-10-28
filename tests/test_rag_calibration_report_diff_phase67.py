from __future__ import annotations

import json
import subprocess
import sys

import pytest

from services.rag.calibration_report_diff import compare_reports, find_regressions

CLI = [sys.executable, "-m", "services.rag.calibration_report_diff_cli"]


def _report(
    *,
    accuracy: float = 1.0,
    macro_f1: float = 1.0,
    grounded_f1: float = 1.0,
    case_results: list[dict] | None = None,
    group_accuracy: float = 1.0,
    support: int = 2,
) -> dict:
    return {
        "schema_version": 1,
        "case_count": support,
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "breakdown": {
            "category": {
                "security": {
                    "case_count": support,
                    "passed": support,
                    "failed": 0,
                    "accuracy": group_accuracy,
                }
            }
        },
        "status_metrics": {
            "grounded": {
                "support": support,
                "precision": grounded_f1,
                "recall": grounded_f1,
                "f1": grounded_f1,
            }
        },
        "case_results": case_results if case_results is not None else [
            {
                "case_id": "case-a",
                "fixture": "case-a.json",
                "expected": "grounded",
                "actual": "grounded",
                "passed": True,
            },
            {
                "case_id": "case-b",
                "fixture": "case-b.json",
                "expected": "grounded",
                "actual": "grounded",
                "passed": True,
            },
        ],
    }


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(CLI + list(args), capture_output=True, text=True, check=False)


def test_compare_reports_returns_metric_group_and_case_deltas():
    baseline = _report()
    current = _report(
        accuracy=0.5,
        macro_f1=0.75,
        grounded_f1=0.8,
        group_accuracy=0.5,
        support=3,
        case_results=[
            {
                "case_id": "case-a",
                "fixture": "case-a.json",
                "expected": "grounded",
                "actual": "unsupported",
                "passed": False,
            },
            {
                "case_id": "case-c",
                "fixture": "case-c.json",
                "expected": "grounded",
                "actual": "grounded",
                "passed": True,
            },
        ],
    )

    comparison = compare_reports(baseline, current)

    assert comparison["metrics"] == {"accuracy": -0.5, "macro_f1": -0.25}
    assert comparison["case_count_delta"] == 1
    assert comparison["status_metrics"]["grounded"]["f1"] == -0.2
    assert comparison["breakdown"]["category"]["security"]["accuracy_delta"] == -0.5
    assert comparison["case_changes"] == {
        "added": ["case-c"],
        "removed": ["case-b"],
        "newly_failing": ["case-a"],
        "recovered": [],
        "changed_prediction": ["case-a"],
    }


def test_regression_gate_reports_metric_drops_and_new_failures():
    comparison = compare_reports(
        _report(),
        _report(
            accuracy=0.8,
            macro_f1=0.7,
            grounded_f1=0.6,
            case_results=[
                {
                    "case_id": "case-a",
                    "fixture": "case-a.json",
                    "expected": "grounded",
                    "actual": "unsupported",
                    "passed": False,
                },
                {
                    "case_id": "case-b",
                    "fixture": "case-b.json",
                    "expected": "grounded",
                    "actual": "grounded",
                    "passed": True,
                },
            ],
        ),
    )

    failures = find_regressions(comparison)

    assert failures == [
        "accuracy dropped by 0.200, exceeding tolerance 0.000",
        "macro F1 dropped by 0.300, exceeding tolerance 0.000",
        "grounded F1 dropped by 0.400, exceeding tolerance 0.000",
        "case newly failing: case-a",
    ]


def test_configured_tolerances_allow_small_metric_drops():
    comparison = compare_reports(
        _report(),
        _report(
            accuracy=0.95,
            macro_f1=0.94,
            grounded_f1=0.93,
            case_results=[
                {
                    "case_id": "case-a",
                    "fixture": "case-a.json",
                    "expected": "grounded",
                    "actual": "grounded",
                    "passed": True,
                },
                {
                    "case_id": "case-b",
                    "fixture": "case-b.json",
                    "expected": "grounded",
                    "actual": "grounded",
                    "passed": True,
                },
            ],
        ),
    )

    assert find_regressions(
        comparison,
        max_accuracy_drop=0.05,
        max_macro_f1_drop=0.06,
        max_class_f1_drop=0.07,
    ) == []


def test_case_level_comparison_is_omitted_for_legacy_reports_without_results():
    baseline = _report()
    current = _report()
    baseline.pop("case_results")
    current.pop("case_results")

    comparison = compare_reports(baseline, current)

    assert comparison["case_changes"] is None
    assert find_regressions(comparison) == []


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda report: report.update(schema_version=2), "unsupported schema_version"),
        (lambda report: report.update(accuracy=float("nan")), "finite and between 0 and 1"),
        (lambda report: report.update(case_count=-1), "non-negative integer"),
        (lambda report: report.update(breakdown=[]), "breakdown must be an object"),
        (
            lambda report: report["case_results"].append(report["case_results"][0]),
            "duplicate case_id",
        ),
        (
            lambda report: report["case_results"][0].update(passed=False),
            "inconsistent passed value",
        ),
    ],
)
def test_invalid_report_data_is_rejected(mutate, message):
    report = _report()
    mutate(report)

    with pytest.raises((TypeError, ValueError), match=message):
        compare_reports(report, _report())


@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan"), float("inf")])
def test_regression_threshold_must_be_finite_and_in_range(value):
    comparison = compare_reports(_report(), _report())

    with pytest.raises(ValueError, match="must be finite and between 0 and 1"):
        find_regressions(comparison, max_accuracy_drop=value)


def test_cli_writes_comparison_report_and_returns_success(tmp_path):
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    output = tmp_path / "out" / "diff.json"
    baseline.write_text(json.dumps(_report()), encoding="utf-8")
    current.write_text(json.dumps(_report()), encoding="utf-8")

    result = _run(
        "--baseline", str(baseline), "--current", str(current), "--output", str(output)
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["passed"] is True
    assert json.loads(output.read_text(encoding="utf-8"))["regressions"] == []


def test_cli_fails_on_regression_and_allows_configured_tolerance(tmp_path):
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    baseline.write_text(json.dumps(_report()), encoding="utf-8")
    current.write_text(json.dumps(_report(accuracy=0.8)), encoding="utf-8")

    failed = _run("--baseline", str(baseline), "--current", str(current))
    tolerated = _run(
        "--baseline", str(baseline), "--current", str(current),
        "--max-accuracy-drop", "0.2",
    )

    assert failed.returncode == 1
    assert "accuracy dropped" in failed.stderr
    assert tolerated.returncode == 0, tolerated.stderr


def test_cli_rejects_invalid_json_with_actionable_error(tmp_path):
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    baseline.write_text("{", encoding="utf-8")
    current.write_text(json.dumps(_report()), encoding="utf-8")

    result = _run("--baseline", str(baseline), "--current", str(current))

    assert result.returncode == 2
    assert "cannot read JSON report" in result.stderr

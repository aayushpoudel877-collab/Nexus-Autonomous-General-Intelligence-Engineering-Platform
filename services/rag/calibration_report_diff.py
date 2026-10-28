"""Compare offline grounding calibration reports and detect regressions.

Report deltas describe fixture agreement only; they are not semantic entailment
or a production safety guarantee.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

_METRICS = ("accuracy", "macro_f1")
_CLASS_METRICS = ("precision", "recall", "f1")


def _validate_report(report: Any, name: str) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise TypeError(f"{name} report must be a JSON object")
    if report.get("schema_version") != 1:
        raise ValueError(f"{name} report has unsupported schema_version")
    for field in ("case_count", "accuracy", "macro_f1", "breakdown", "status_metrics"):
        if field not in report:
            raise ValueError(f"{name} report is missing {field}")
    count = report["case_count"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError(f"{name} report case_count must be a non-negative integer")
    for field in _METRICS:
        value = report[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} report {field} must be numeric")
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{name} report {field} must be finite and between 0 and 1")
    for field in ("breakdown", "status_metrics"):
        if not isinstance(report[field], dict):
            raise TypeError(f"{name} report {field} must be an object")
    for status, values in report["status_metrics"].items():
        if not isinstance(status, str) or not isinstance(values, dict):
            raise TypeError(f"{name} report status_metrics entries must be objects")
        for metric in _CLASS_METRICS:
            if metric in values:
                value = values[metric]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise TypeError(f"{name} status metric {status}.{metric} must be numeric")
                if not math.isfinite(value) or not 0 <= value <= 1:
                    raise ValueError(
                        f"{name} status metric {status}.{metric} must be between 0 and 1"
                    )
    for dimension, groups in report["breakdown"].items():
        if not isinstance(dimension, str) or not isinstance(groups, dict):
            raise TypeError(f"{name} breakdown dimensions must contain objects")
        for group, values in groups.items():
            if not isinstance(group, str) or not isinstance(values, dict):
                raise TypeError(f"{name} breakdown groups must contain objects")
            if "accuracy" in values:
                value = values["accuracy"]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise TypeError(f"{name} group {dimension}.{group} accuracy must be numeric")
                if not math.isfinite(value) or not 0 <= value <= 1:
                    raise ValueError(
                        f"{name} group {dimension}.{group} accuracy must be between 0 and 1"
                    )
    _case_index(report, name)
    return report


def _case_index(report: Mapping[str, Any], name: str) -> dict[str, dict[str, Any]] | None:
    if "case_results" not in report:
        return None
    results = report["case_results"]
    if not isinstance(results, list):
        raise TypeError(f"{name} report case_results must be a list")
    indexed: dict[str, dict[str, Any]] = {}
    for item in results:
        if not isinstance(item, dict):
            raise TypeError(f"{name} case_results entries must be objects")
        case_id = item.get("case_id")
        expected = item.get("expected")
        actual = item.get("actual")
        passed = item.get("passed")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"{name} case_results require a non-empty case_id")
        if case_id in indexed:
            raise ValueError(f"{name} report contains duplicate case_id: {case_id}")
        if not isinstance(expected, str) or not isinstance(actual, str):
            raise TypeError(f"{name} case {case_id} expected and actual must be strings")
        if not isinstance(passed, bool):
            raise TypeError(f"{name} case {case_id} passed must be a boolean")
        if passed != (expected == actual):
            raise ValueError(f"{name} case {case_id} has inconsistent passed value")
        indexed[case_id] = item
    return indexed


def _delta(current: float, baseline: float) -> float:
    return round(float(current) - float(baseline), 10)


def compare_reports(baseline: Any, current: Any) -> dict[str, Any]:
    """Compare two schema-v1 reports; positive deltas mean the current value rose."""
    before = _validate_report(baseline, "baseline")
    after = _validate_report(current, "current")
    metric_deltas = {
        field: _delta(after[field], before[field]) for field in _METRICS
    }
    statuses = sorted(set(before["status_metrics"]) | set(after["status_metrics"]))
    status_deltas: dict[str, Any] = {}
    for status in statuses:
        old = before["status_metrics"].get(status, {})
        new = after["status_metrics"].get(status, {})
        status_deltas[status] = {}
        for metric in _CLASS_METRICS:
            old_value = old.get(metric, 0.0)
            new_value = new.get(metric, 0.0)
            status_deltas[status][metric] = _delta(new_value, old_value)
        status_deltas[status]["support_delta"] = int(new.get("support", 0)) - int(
            old.get("support", 0)
        )

    breakdown_deltas: dict[str, Any] = {}
    dimensions = sorted(set(before["breakdown"]) | set(after["breakdown"]))
    for dimension in dimensions:
        old_groups = before["breakdown"].get(dimension, {})
        new_groups = after["breakdown"].get(dimension, {})
        breakdown_deltas[dimension] = {}
        for group in sorted(set(old_groups) | set(new_groups)):
            old = old_groups.get(group, {})
            new = new_groups.get(group, {})
            breakdown_deltas[dimension][group] = {
                "baseline_present": group in old_groups,
                "current_present": group in new_groups,
                "case_count_delta": int(new.get("case_count", 0)) - int(
                    old.get("case_count", 0)
                ),
                "accuracy_delta": _delta(new.get("accuracy", 0.0), old.get("accuracy", 0.0)),
            }

    old_cases = _case_index(before, "baseline")
    new_cases = _case_index(after, "current")
    case_changes: dict[str, Any] | None = None
    if old_cases is not None and new_cases is not None:
        shared = set(old_cases) & set(new_cases)
        case_changes = {
            "added": sorted(set(new_cases) - set(old_cases)),
            "removed": sorted(set(old_cases) - set(new_cases)),
            "newly_failing": sorted(
                case_id for case_id in shared
                if old_cases[case_id]["passed"] and not new_cases[case_id]["passed"]
            ),
            "recovered": sorted(
                case_id for case_id in shared
                if not old_cases[case_id]["passed"] and new_cases[case_id]["passed"]
            ),
            "changed_prediction": sorted(
                case_id for case_id in shared
                if old_cases[case_id]["actual"] != new_cases[case_id]["actual"]
            ),
        }
    return {
        "schema_version": 1,
        "baseline_case_count": before["case_count"],
        "current_case_count": after["case_count"],
        "case_count_delta": after["case_count"] - before["case_count"],
        "metrics": metric_deltas,
        "status_metrics": status_deltas,
        "breakdown": breakdown_deltas,
        "case_changes": case_changes,
        "interpretation": (
            "Deltas compare fixture reports only; they do not establish semantic "
            "entailment, factual correctness, or production safety."
        ),
    }


def find_regressions(
    comparison: Mapping[str, Any],
    *,
    max_accuracy_drop: float = 0.0,
    max_macro_f1_drop: float = 0.0,
    max_class_f1_drop: float = 0.0,
    fail_on_new_case_failures: bool = True,
) -> list[str]:
    """Return deterministic gate failures for configured maximum metric drops."""
    thresholds = {
        "max_accuracy_drop": max_accuracy_drop,
        "max_macro_f1_drop": max_macro_f1_drop,
        "max_class_f1_drop": max_class_f1_drop,
    }
    for name, value in thresholds.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be numeric")
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{name} must be finite and between 0 and 1")
    failures: list[str] = []
    if comparison["metrics"]["accuracy"] < -max_accuracy_drop:
        failures.append(
            f"accuracy dropped by {-comparison['metrics']['accuracy']:.3f}, "
            f"exceeding tolerance {max_accuracy_drop:.3f}"
        )
    if comparison["metrics"]["macro_f1"] < -max_macro_f1_drop:
        failures.append(
            f"macro F1 dropped by {-comparison['metrics']['macro_f1']:.3f}, "
            f"exceeding tolerance {max_macro_f1_drop:.3f}"
        )
    for status, metrics in comparison["status_metrics"].items():
        if metrics["f1"] < -max_class_f1_drop:
            failures.append(
                f"{status} F1 dropped by {-metrics['f1']:.3f}, "
                f"exceeding tolerance {max_class_f1_drop:.3f}"
            )
    changes = comparison.get("case_changes")
    if fail_on_new_case_failures and changes:
        for case_id in changes["newly_failing"]:
            failures.append(f"case newly failing: {case_id}")
    return failures

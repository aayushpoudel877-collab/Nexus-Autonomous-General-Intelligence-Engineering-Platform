"""Lifecycle policy for ML runs, evaluations and human-reviewed model records."""

from datetime import datetime, timezone
from math import isfinite
from typing import Any

_RUN_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"running", "cancelled"},
    "running": {"succeeded", "failed", "cancelled"},
    "succeeded": set(),
    "failed": set(),
    "cancelled": set(),
}

_MODEL_TRANSITIONS: dict[str, set[str]] = {
    "candidate": {"validated", "archived"},
    "validated": {"approved", "archived"},
    "approved": {"archived"},
    "archived": set(),
}

_EVALUATION_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"running", "cancelled"},
    "running": {"passed", "failed", "cancelled"},
    "passed": set(),
    "failed": set(),
    "cancelled": set(),
}


def _ensure_transition(current: str, requested: str, transitions: dict[str, set[str]], label: str) -> None:
    if current == requested:
        return
    if requested not in transitions.get(current, set()):
        raise ValueError(f"Cannot change {label} status from '{current}' to '{requested}'")


def ensure_run_transition(current: str, requested: str) -> None:
    _ensure_transition(current, requested, _RUN_TRANSITIONS, "training run")


def ensure_model_transition(current: str, requested: str) -> None:
    _ensure_transition(current, requested, _MODEL_TRANSITIONS, "model")


def ensure_evaluation_transition(current: str, requested: str) -> None:
    _ensure_transition(current, requested, _EVALUATION_TRANSITIONS, "evaluation")


def evaluation_criteria_met(
    metrics: dict[str, Any], criteria: dict[str, Any]
) -> tuple[bool, list[str]]:
    """Compare recorded numeric metrics with explicit minimum/maximum criteria."""
    if not criteria:
        return False, ["At least one numeric evaluation criterion is required"]

    issues: list[str] = []
    for metric_name, criterion in criteria.items():
        actual = metrics.get(metric_name)
        if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not isfinite(actual):
            issues.append(f"Metric '{metric_name}' must have a finite numeric result")
            continue
        if not isinstance(criterion, dict):
            issues.append(f"Criterion '{metric_name}' must define min and/or max")
            continue
        minimum = criterion.get("min")
        maximum = criterion.get("max")
        if minimum is None and maximum is None:
            issues.append(f"Criterion '{metric_name}' must define min and/or max")
            continue
        if minimum is not None and actual < minimum:
            issues.append(f"Metric '{metric_name}' is below its minimum of {minimum}")
        if maximum is not None and actual > maximum:
            issues.append(f"Metric '{metric_name}' is above its maximum of {maximum}")
    return not issues, issues


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

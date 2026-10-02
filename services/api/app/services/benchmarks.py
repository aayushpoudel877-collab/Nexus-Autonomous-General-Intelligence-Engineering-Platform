"""Pure comparison logic for reported benchmark metrics."""

from math import isfinite
from typing import Any


def compare_metrics(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    criteria: dict[str, dict[str, Any]],
) -> tuple[bool, dict[str, float], list[str]]:
    """Compare caller-reported metrics; this function does not execute models."""
    if not criteria:
        return False, {}, ["At least one benchmark criterion is required"]
    deltas: dict[str, float] = {}
    issues: list[str] = []
    for name, criterion in criteria.items():
        before, after = baseline.get(name), candidate.get(name)
        if (
            isinstance(before, bool) or not isinstance(before, (int, float)) or not isfinite(before)
            or isinstance(after, bool) or not isinstance(after, (int, float)) or not isfinite(after)
        ):
            issues.append(f"Metric '{name}' must have finite numeric baseline and candidate values")
            continue
        delta = float(after) - float(before)
        deltas[name] = delta
        direction = criterion.get("direction")
        minimum = criterion.get("minimum_improvement", 0)
        improvement = delta if direction == "maximize" else -delta if direction == "minimize" else None
        if improvement is None:
            issues.append(f"Criterion '{name}' must use maximize or minimize direction")
        elif improvement < minimum:
            issues.append(f"Metric '{name}' improved by {improvement:g}, below required {minimum:g}")
    return not issues, deltas, issues

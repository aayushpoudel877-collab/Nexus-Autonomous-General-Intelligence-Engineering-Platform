"""Offline evaluation of proposed retrieval tool plans against reviewed allowlists."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
import re

MAX_TOOL_PLAN_CASES = 5_000
MAX_TOOLS_PER_CASE = 32
_LABEL_LIMIT = 80
_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")


@dataclass(frozen=True, slots=True)
class ToolPlanEvaluationCase:
    """One reviewed tool-selection decision; no raw query or evidence text is required."""

    case_id: str
    expected_tool_names: tuple[str, ...]
    proposed_tool_names: tuple[str, ...]
    allowed_tool_names: tuple[str, ...]
    language: str = "und"
    risk_category: str = "general"

    def __post_init__(self) -> None:
        for name in ("case_id", "language", "risk_category"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > _LABEL_LIMIT:
                raise ValueError(f"{name} must be non-empty and at most {_LABEL_LIMIT} characters")
        for name in ("expected_tool_names", "proposed_tool_names", "allowed_tool_names"):
            values = getattr(self, name)
            if not isinstance(values, tuple):
                raise TypeError(f"{name} must be a tuple")
            if len(values) > MAX_TOOLS_PER_CASE:
                raise ValueError(f"{name} contains too many tools")
            if any(not isinstance(item, str) or not _TOOL_NAME.fullmatch(item) for item in values):
                raise ValueError(f"{name} contains an invalid tool name")
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must contain unique tool names")
        if not set(self.expected_tool_names).issubset(self.allowed_tool_names):
            raise ValueError("expected tools must be included in the allowed tool set")


def _metrics(cases: Sequence[ToolPlanEvaluationCase]) -> dict[str, float | int]:
    true_positive = false_positive = false_negative = 0
    forbidden_attempts = 0
    forbidden_case_ids: list[str] = []
    false_positive_case_ids: list[str] = []
    false_negative_case_ids: list[str] = []

    for case in cases:
        expected = set(case.expected_tool_names)
        proposed = set(case.proposed_tool_names)
        allowed = set(case.allowed_tool_names)
        true_positive += len(expected & proposed)
        extras = proposed - expected
        missing = expected - proposed
        false_positive += len(extras)
        false_negative += len(missing)
        forbidden = proposed - allowed
        forbidden_attempts += len(forbidden)
        if forbidden:
            forbidden_case_ids.append(case.case_id)
        if extras:
            false_positive_case_ids.append(case.case_id)
        if missing:
            false_negative_case_ids.append(case.case_id)

    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "forbidden_tool_attempts": forbidden_attempts,
        "forbidden_tool_case_ids": sorted(forbidden_case_ids),
        "false_positive_case_ids": sorted(false_positive_case_ids),
        "false_negative_case_ids": sorted(false_negative_case_ids),
    }


def evaluate_tool_plan_cases(
    cases: Sequence[ToolPlanEvaluationCase],
) -> dict[str, object]:
    """Return deterministic tool-selection metrics and language/risk slices."""
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)):
        raise TypeError("cases must be a sequence of ToolPlanEvaluationCase values")
    if not cases:
        raise ValueError("at least one tool-plan case is required")
    if len(cases) > MAX_TOOL_PLAN_CASES:
        raise ValueError("tool-plan case count exceeds the configured limit")
    if any(not isinstance(case, ToolPlanEvaluationCase) for case in cases):
        raise TypeError("cases must contain ToolPlanEvaluationCase values")
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("tool-plan case IDs must be unique")

    by_language: dict[str, list[ToolPlanEvaluationCase]] = defaultdict(list)
    by_risk: dict[str, list[ToolPlanEvaluationCase]] = defaultdict(list)
    for case in cases:
        by_language[case.language].append(case)
        by_risk[case.risk_category].append(case)

    return {
        "evaluator_version": "tool-plan-selection-v1",
        "case_count": len(cases),
        "aggregate": _metrics(cases),
        "by_language": {
            label: _metrics(group) for label, group in sorted(by_language.items())
        },
        "by_risk_category": {
            label: _metrics(group) for label, group in sorted(by_risk.items())
        },
    }

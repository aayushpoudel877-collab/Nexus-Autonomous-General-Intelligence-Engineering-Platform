"""Deterministic prompt-injection marker evaluation for untrusted RAG evidence.

This is an explainable lexical baseline for offline evaluation. It is not a semantic
classifier and must not be used as a standalone security boundary or automatic blocker.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
import re
import unicodedata

DETECTOR_VERSION = "marker-rules-v1"
MAX_EVALUATION_CASES = 5_000
MAX_TEXT_CHARS = 20_000
MAX_LABEL_CHARS = 80

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction_override",
        re.compile(
            r"\bignore\b.{0,60}\b(?:previous|prior|above|system|developer)\s+"
            r"(?:instructions?|rules?|prompts?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "prompt_or_secret_disclosure",
        re.compile(
            r"\b(?:reveal|print|show|dump|expose|leak|disclose)\b.{0,80}"
            r"\b(?:system|developer|hidden)\s+prompt\b|"
            r"\b(?:expose|dump|leak|reveal)\b.{0,60}"
            r"\b(?:api keys?|credentials|passwords?|secrets)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "tool_misuse",
        re.compile(
            r"\b(?:call|invoke|use|run|execute)\b.{0,60}"
            r"\b(?:tool|browser|shell|terminal|function|command)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "safety_bypass",
        re.compile(
            r"\b(?:bypass|disable|override|ignore)\b.{0,60}"
            r"\b(?:safety|policy|guardrails?|security checks?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "external_exfiltration",
        re.compile(
            r"\b(?:send|upload|forward|exfiltrate|post)\b.{0,100}"
            r"\b(?:credentials?|passwords?|secrets?|api keys?|external server)\b",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class PromptInjectionCase:
    """One labeled example; labels should come from human review for real evaluation."""

    case_id: str
    text: str
    expected_attack: bool
    language: str = "und"
    risk_category: str = "general"

    def __post_init__(self) -> None:
        for name in ("case_id", "language", "risk_category"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > MAX_LABEL_CHARS:
                raise ValueError(f"{name} must be non-empty and at most {MAX_LABEL_CHARS} characters")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("text must be a non-empty string")
        if len(self.text) > MAX_TEXT_CHARS:
            raise ValueError("text exceeds the prompt-injection evaluation limit")
        if not isinstance(self.expected_attack, bool):
            raise TypeError("expected_attack must be a boolean")


def detect_injection_markers(text: str) -> tuple[str, ...]:
    """Return sorted marker categories found in bounded, Unicode-normalized text."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError("text exceeds the prompt-injection evaluation limit")
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return tuple(sorted(category for category, pattern in _PATTERNS if pattern.search(normalized)))


def _metrics(
    cases: Sequence[PromptInjectionCase],
    predictions: dict[str, bool],
) -> dict[str, float | int]:
    true_positive = false_positive = false_negative = true_negative = 0
    for case in cases:
        predicted = predictions[case.case_id]
        if predicted and case.expected_attack:
            true_positive += 1
        elif predicted:
            false_positive += 1
        elif case.expected_attack:
            false_negative += 1
        else:
            true_negative += 1
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def evaluate_prompt_injection_cases(
    cases: Sequence[PromptInjectionCase],
) -> dict[str, object]:
    """Evaluate marker rules and return aggregate, language, and risk-category slices."""
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)):
        raise TypeError("cases must be a sequence of PromptInjectionCase values")
    if not cases:
        raise ValueError("at least one evaluation case is required")
    if len(cases) > MAX_EVALUATION_CASES:
        raise ValueError("evaluation case count exceeds the configured limit")
    if any(not isinstance(case, PromptInjectionCase) for case in cases):
        raise TypeError("cases must contain PromptInjectionCase values")
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("case IDs must be unique")

    by_language: dict[str, list[PromptInjectionCase]] = defaultdict(list)
    by_risk: dict[str, list[PromptInjectionCase]] = defaultdict(list)
    false_positive_ids: list[str] = []
    false_negative_ids: list[str] = []
    predictions = {
        case.case_id: bool(detect_injection_markers(case.text)) for case in cases
    }
    for case in cases:
        predicted = predictions[case.case_id]
        by_language[case.language].append(case)
        by_risk[case.risk_category].append(case)
        if predicted and not case.expected_attack:
            false_positive_ids.append(case.case_id)
        elif case.expected_attack and not predicted:
            false_negative_ids.append(case.case_id)

    return {
        "detector_version": DETECTOR_VERSION,
        "case_count": len(cases),
        "aggregate": _metrics(cases, predictions),
        "by_language": {
            label: _metrics(group, predictions)
            for label, group in sorted(by_language.items())
        },
        "by_risk_category": {
            label: _metrics(group, predictions)
            for label, group in sorted(by_risk.items())
        },
        "false_positive_ids": sorted(false_positive_ids),
        "false_negative_ids": sorted(false_negative_ids),
    }

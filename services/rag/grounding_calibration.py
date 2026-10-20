"""Evaluate lexical claim-grounding behavior against a versioned regression corpus.

This module measures agreement with expected fixture labels. It is an offline
regression tool, not a semantic-entailment or production safety guarantee.
"""
from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from services.rag.grounding import ClaimEvidence, GroundingClaim, LexicalGroundingVerifier

_ALLOWED_STATUSES = frozenset({"grounded", "unsupported", "contradictory", "inconclusive"})


def load_case_files(directory: str | Path) -> list[dict[str, Any]]:
    """Load and validate sorted JSON case files from a corpus directory."""
    root = Path(directory)
    if not root.is_dir():
        raise ValueError(f"fixture directory does not exist: {root}")
    paths = sorted(root.glob("*.json"))
    if not paths:
        raise ValueError(f"no JSON grounding fixtures found in {root}")
    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for path in paths:
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid fixture {path.name}: {exc}") from exc
        if not isinstance(case, dict):
            raise TypeError(f"fixture {path.name} must contain a JSON object")
        case = dict(case)
        case.setdefault("case_id", path.stem)
        case["_fixture"] = path.name
        _validate_case(case)
        if case["case_id"] in seen_ids:
            raise ValueError(f"duplicate case_id: {case['case_id']}")
        seen_ids.add(case["case_id"])
        cases.append(case)
    return cases


def _validate_case(case: dict[str, Any]) -> None:
    required = {"case_id", "claim", "citations", "evidence", "expected_status"}
    missing = required - case.keys()
    if missing:
        raise ValueError(f"fixture is missing fields: {', '.join(sorted(missing))}")
    for field in ("case_id", "claim"):
        if not isinstance(case[field], str) or not case[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if not isinstance(case["citations"], list) or not all(
        isinstance(value, str) for value in case["citations"]
    ):
        raise ValueError("citations must be a list of strings")
    if not isinstance(case["evidence"], list) or not case["evidence"]:
        raise ValueError("evidence must be a non-empty list")
    for item in case["evidence"]:
        if not isinstance(item, dict) or not isinstance(item.get("evidence_id"), str):
            raise TypeError("each evidence item needs a string evidence_id")
        if not isinstance(item.get("text"), str):
            raise TypeError("each evidence item needs string text")
    if (
        not isinstance(case["expected_status"], str)
        or case["expected_status"] not in _ALLOWED_STATUSES
    ):
        raise ValueError(f"expected_status must be one of {sorted(_ALLOWED_STATUSES)}")


def evaluate_cases(cases: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Run cases and return deterministic counts, confusion matrix, and failures."""
    verifier = LexicalGroundingVerifier()
    confusion: Counter[str] = Counter()
    failures: list[dict[str, str]] = []
    count = 0
    for case in cases:
        _validate_case(case)
        claim = GroundingClaim(case["case_id"], case["claim"], tuple(case["citations"]))
        evidence = [
            ClaimEvidence(item["evidence_id"], item["text"])
            for item in case["evidence"]
        ]
        report = verifier.assess([claim], evidence)
        actual = report.assessments[0].status
        expected = case["expected_status"]
        confusion[f"{expected}->{actual}"] += 1
        count += 1
        if actual != expected:
            failures.append({
                "case_id": case["case_id"],
                "fixture": str(case.get("_fixture", "")),
                "expected": expected,
                "actual": actual,
            })
    correct = count - len(failures)
    return {
        "schema_version": 1,
        "case_count": count,
        "passed": correct,
        "failed": len(failures),
        "accuracy": correct / count if count else 0.0,
        "confusion": dict(sorted(confusion.items())),
        "failures": failures,
        "interpretation": (
            "Fixture agreement measures regression consistency only; "
            "lexical grounding does not establish semantic entailment."
        ),
    }

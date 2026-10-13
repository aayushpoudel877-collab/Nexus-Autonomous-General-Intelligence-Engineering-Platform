"""Human-label comparison for claim grounding and citation integrity."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .evaluation import _read_jsonl
from .grounding import ClaimEvidence, GroundingClaim, LexicalGroundingVerifier


@dataclass(frozen=True, slots=True)
class GroundingEvaluationCase:
    """One reviewed binary support judgement with the source IDs actually cited."""

    case_id: str
    claim_text: str
    evidence_id: str
    evidence_text: str
    cited_evidence_ids: tuple[str, ...]
    expected_supported: bool
    language: str = "und"
    risk_category: str = "general"

    def __post_init__(self) -> None:
        for name in ("case_id", "claim_text", "evidence_id", "evidence_text", "language", "risk_category"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.expected_supported, bool):
            raise ValueError("expected_supported must be boolean")
        if len(set(self.cited_evidence_ids)) != len(self.cited_evidence_ids):
            raise ValueError("cited evidence IDs must be unique")
        if any(not isinstance(item, str) or not item.strip() for item in self.cited_evidence_ids):
            raise ValueError("cited evidence IDs must be non-empty strings")


def load_grounding_dataset(path: str | Path) -> tuple[GroundingEvaluationCase, ...]:
    """Load a bounded claim-level benchmark with explicit human support labels."""
    required = {
        "case_id", "claim_text", "evidence_id", "evidence_text",
        "cited_evidence_ids", "expected_supported",
    }
    allowed = required | {"language", "risk_category"}
    cases: list[GroundingEvaluationCase] = []
    seen: set[str] = set()
    for row in _read_jsonl(path):
        unknown = set(row) - allowed
        missing = required - set(row)
        if unknown or missing:
            raise ValueError(f"grounding record has unknown or missing fields: {sorted(unknown | missing)}")
        if not isinstance(row["cited_evidence_ids"], list):
            raise ValueError("cited_evidence_ids must be a JSON array")
        case = GroundingEvaluationCase(
            case_id=row["case_id"],
            claim_text=row["claim_text"],
            evidence_id=row["evidence_id"],
            evidence_text=row["evidence_text"],
            cited_evidence_ids=tuple(row["cited_evidence_ids"]),
            expected_supported=row["expected_supported"],
            language=row.get("language", "und"),
            risk_category=row.get("risk_category", "general"),
        )
        if case.case_id in seen:
            raise ValueError(f"duplicate grounding case_id: {case.case_id}")
        seen.add(case.case_id)
        cases.append(case)
    if not cases:
        raise ValueError("grounding dataset must contain at least one case")
    return tuple(cases)


def evaluate_grounding_cases(
    cases: tuple[GroundingEvaluationCase, ...] | list[GroundingEvaluationCase],
    *,
    verifier: LexicalGroundingVerifier | None = None,
) -> dict[str, Any]:
    """Report confusion metrics and false-positive/negative case IDs.

    Unknown or missing citations fail closed as unsupported predictions. A
    'grounded' prediction remains a lexical signal, not proof of semantic entailment.
    """
    if not cases:
        raise ValueError("at least one grounding case is required")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("grounding case IDs must be unique")
    active_verifier = verifier or LexicalGroundingVerifier()
    tp = fp = tn = fn = valid_citations = 0
    statuses: dict[str, int] = {}
    false_positives: list[str] = []
    false_negatives: list[str] = []
    by_language: dict[str, list[GroundingEvaluationCase]] = {}
    by_risk: dict[str, list[GroundingEvaluationCase]] = {}
    for case in cases:
        by_language.setdefault(case.language, []).append(case)
        by_risk.setdefault(case.risk_category, []).append(case)
        citation_valid = bool(case.cited_evidence_ids) and set(case.cited_evidence_ids) <= {case.evidence_id}
        valid_citations += int(citation_valid)
        if citation_valid:
            assessment = active_verifier.assess(
                [GroundingClaim(case.case_id, case.claim_text, case.cited_evidence_ids)],
                [ClaimEvidence(case.evidence_id, case.evidence_text)],
            ).assessments[0]
            status = assessment.status
        else:
            status = "unsupported"
        statuses[status] = statuses.get(status, 0) + 1
        predicted_supported = status == "grounded"
        if predicted_supported and case.expected_supported:
            tp += 1
        elif predicted_supported and not case.expected_supported:
            fp += 1
            false_positives.append(case.case_id)
        elif not predicted_supported and case.expected_supported:
            fn += 1
            false_negatives.append(case.case_id)
        else:
            tn += 1

    count = len(cases)
    return {
        "case_count": count,
        "confusion_matrix": {"true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn},
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
        "false_negative_rate": fn / (fn + tp) if fn + tp else 0.0,
        "accuracy": (tp + tn) / count,
        "citation_validity_rate": valid_citations / count,
        "status_counts": statuses,
        "false_positive_case_ids": false_positives,
        "false_negative_case_ids": false_negatives,
        "slices": {
            "language": {key: _evaluate_slice(value, active_verifier) for key, value in sorted(by_language.items())},
            "risk_category": {key: _evaluate_slice(value, active_verifier) for key, value in sorted(by_risk.items())},
        },
        "interpretation": "Lexical heuristic evaluation only; labels and metrics do not establish semantic entailment.",
    }


def _evaluate_slice(
    cases: list[GroundingEvaluationCase],
    verifier: LexicalGroundingVerifier,
) -> dict[str, float | int]:
    tp = fp = tn = fn = valid_citations = 0
    for case in cases:
        valid = bool(case.cited_evidence_ids) and set(case.cited_evidence_ids) <= {case.evidence_id}
        valid_citations += int(valid)
        status = (
            verifier.assess(
                [GroundingClaim(case.case_id, case.claim_text, case.cited_evidence_ids)],
                [ClaimEvidence(case.evidence_id, case.evidence_text)],
            ).assessments[0].status
            if valid else "unsupported"
        )
        predicted = status == "grounded"
        if predicted and case.expected_supported:
            tp += 1
        elif predicted and not case.expected_supported:
            fp += 1
        elif not predicted and case.expected_supported:
            fn += 1
        else:
            tn += 1
    count = len(cases)
    return {
        "case_count": count,
        "accuracy": (tp + tn) / count,
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
        "false_negative_rate": fn / (fn + tp) if fn + tp else 0.0,
        "citation_validity_rate": valid_citations / count,
    }

"""Offline, reproducible evaluation for RAG retrieval experiments.

Golden-set evaluation is provider-independent and bounded. It evaluates ranked chunk
IDs against reviewed relevance labels; it does not call providers or prove answer truth.
The original in-memory evaluation helpers remain available for compatibility.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .grounding import validate_citations
from .ranking import ranking_metrics
from .retrieval import Evidence, RetrievalHit

MAX_DATASET_BYTES = 10 * 1024 * 1024
MAX_CASES = 20_000
MAX_LINE_BYTES = 256 * 1024
MAX_TEXT_LENGTH = 20_000
MAX_LABELS_PER_CASE = 5_000
DEFAULT_METRICS = ("precision_at_k", "recall_at_k", "reciprocal_rank", "ndcg_at_k")


@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    recall_at_k: float
    reciprocal_rank: float
    retrieved: int
    relevant_found: int


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """Reviewed, privacy-safe golden query and relevance judgement."""

    case_id: str
    tenant_id: str
    query: str
    relevant_chunk_ids: tuple[str, ...]
    language: str = "und"
    risk_category: str = "general"
    reviewer_notes: str = ""

    def __post_init__(self) -> None:
        for name in ("case_id", "tenant_id", "query", "language", "risk_category"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.reviewer_notes, str):
            raise ValueError("reviewer_notes must be a string")
        if len(self.query) > MAX_TEXT_LENGTH or len(self.reviewer_notes) > MAX_TEXT_LENGTH:
            raise ValueError("query or reviewer_notes exceeds maximum length")
        if not self.relevant_chunk_ids:
            raise ValueError("each case requires at least one relevant chunk ID")
        if len(self.relevant_chunk_ids) > MAX_LABELS_PER_CASE:
            raise ValueError("too many relevant chunk IDs")
        if any(not isinstance(item, str) or not item.strip() for item in self.relevant_chunk_ids):
            raise ValueError("relevant chunk IDs must be non-empty strings")
        if len(set(self.relevant_chunk_ids)) != len(self.relevant_chunk_ids):
            raise ValueError("relevant chunk IDs must be unique")


@dataclass(frozen=True, slots=True)
class EvaluationPrediction:
    """One run's ranked chunk IDs for one golden case."""

    run_name: str
    case_id: str
    ranked_chunk_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.run_name, str) or not self.run_name.strip():
            raise ValueError("run_name is required")
        if not isinstance(self.case_id, str) or not self.case_id.strip():
            raise ValueError("case_id is required")
        if any(not isinstance(item, str) or not item.strip() for item in self.ranked_chunk_ids):
            raise ValueError("ranked chunk IDs must be non-empty strings")
        if len(set(self.ranked_chunk_ids)) != len(self.ranked_chunk_ids):
            raise ValueError("ranked chunk IDs must be unique within a prediction")


@dataclass(frozen=True, slots=True)
class EvaluationThresholds:
    """Maximum allowed absolute drop from baseline for each aggregate metric."""

    max_precision_drop: float = 0.05
    max_recall_drop: float = 0.05
    max_ndcg_drop: float = 0.05

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be finite and between 0 and 1")


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.is_file():
        raise ValueError(f"input file does not exist: {file_path}")
    if file_path.stat().st_size > MAX_DATASET_BYTES:
        raise ValueError("JSONL input exceeds maximum file size")
    records: list[dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if len(line.encode("utf-8")) > MAX_LINE_BYTES:
                raise ValueError(f"line {line_number} exceeds maximum size")
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on line {line_number}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"line {line_number} must contain a JSON object")
            records.append(value)
            if len(records) > MAX_CASES:
                raise ValueError("JSONL input contains too many records")
    return records


def load_golden_dataset(path: str | Path) -> tuple[EvaluationCase, ...]:
    """Load a bounded JSONL golden set, rejecting ambiguous/duplicate records."""
    cases: list[EvaluationCase] = []
    seen: set[str] = set()
    required = {"case_id", "tenant_id", "query", "relevant_chunk_ids"}
    allowed = required | {"language", "risk_category", "reviewer_notes"}
    for row in _read_jsonl(path):
        unknown = set(row) - allowed
        missing = required - set(row)
        if unknown or missing:
            raise ValueError(f"dataset record has unknown or missing fields: {sorted(unknown | missing)}")
        labels = row["relevant_chunk_ids"]
        if not isinstance(labels, list):
            raise ValueError("relevant_chunk_ids must be a JSON array")
        case = EvaluationCase(
            case_id=row["case_id"],
            tenant_id=row["tenant_id"],
            query=row["query"],
            relevant_chunk_ids=tuple(labels),
            language=row.get("language", "und"),
            risk_category=row.get("risk_category", "general"),
            reviewer_notes=row.get("reviewer_notes", ""),
        )
        if case.case_id in seen:
            raise ValueError(f"duplicate case_id: {case.case_id}")
        seen.add(case.case_id)
        cases.append(case)
    if not cases:
        raise ValueError("golden dataset must contain at least one case")
    return tuple(cases)


def load_predictions(path: str | Path) -> tuple[EvaluationPrediction, ...]:
    """Load one JSONL record per (run, case); duplicate pairs fail closed."""
    predictions: list[EvaluationPrediction] = []
    seen: set[tuple[str, str]] = set()
    required = {"run_name", "case_id", "ranked_chunk_ids"}
    for row in _read_jsonl(path):
        if set(row) != required or not isinstance(row["ranked_chunk_ids"], list):
            raise ValueError("prediction record must contain run_name, case_id, ranked_chunk_ids")
        prediction = EvaluationPrediction(
            run_name=row["run_name"],
            case_id=row["case_id"],
            ranked_chunk_ids=tuple(row["ranked_chunk_ids"]),
        )
        key = (prediction.run_name, prediction.case_id)
        if key in seen:
            raise ValueError(f"duplicate prediction for run/case: {key}")
        seen.add(key)
        predictions.append(prediction)
    if not predictions:
        raise ValueError("prediction file must contain at least one record")
    return tuple(predictions)


def _aggregate(
    cases: Sequence[EvaluationCase],
    rankings: Mapping[str, Sequence[str]],
    *,
    k: int,
) -> dict[str, float | int]:
    per_case = [
        ranking_metrics(rankings.get(case.case_id, ()), set(case.relevant_chunk_ids), k=k)
        for case in cases
    ]
    result: dict[str, float | int] = {
        metric: sum(row[metric] for row in per_case) / len(per_case)
        for metric in DEFAULT_METRICS
    }
    result["case_count"] = len(cases)
    result["empty_result_rate"] = (
        sum(not rankings.get(case.case_id, ()) for case in cases) / len(cases)
    )
    return result


def _slices(
    cases: Sequence[EvaluationCase],
    rankings: Mapping[str, Sequence[str]],
    *,
    k: int,
) -> dict[str, dict[str, dict[str, float | int]]]:
    dimensions: dict[str, dict[str, list[EvaluationCase]]] = {
        "language": defaultdict(list),
        "risk_category": defaultdict(list),
        "tenant_id": defaultdict(list),
    }
    for case in cases:
        dimensions["language"][case.language].append(case)
        dimensions["risk_category"][case.risk_category].append(case)
        dimensions["tenant_id"][case.tenant_id].append(case)
    return {
        dimension: {
            value: _aggregate(group, rankings, k=k)
            for value, group in sorted(groups.items())
        }
        for dimension, groups in dimensions.items()
    }


def evaluate_golden_runs(
    cases: Sequence[EvaluationCase],
    predictions: Sequence[EvaluationPrediction],
    *,
    k: int = 5,
) -> dict[str, Any]:
    """Compute per-run aggregate and language/risk/tenant slice metrics.

    Missing predictions count as empty retrievals. Predictions for unknown case IDs
    are rejected so evaluation cannot silently mix incompatible datasets.
    """
    if not cases:
        raise ValueError("at least one evaluation case is required")
    if not 1 <= k <= 100:
        raise ValueError("k must be between 1 and 100")
    case_by_id = {case.case_id: case for case in cases}
    if len(case_by_id) != len(cases):
        raise ValueError("case IDs must be unique")
    unknown = sorted({item.case_id for item in predictions} - set(case_by_id))
    if unknown:
        raise ValueError(f"predictions reference unknown case IDs: {unknown}")
    prediction_keys = [(item.run_name, item.case_id) for item in predictions]
    if len(prediction_keys) != len(set(prediction_keys)):
        raise ValueError("duplicate prediction for run/case")
    run_names = sorted({item.run_name for item in predictions})
    if not run_names:
        raise ValueError("at least one named run is required")
    report: dict[str, Any] = {
        "schema_version": 1,
        "k": k,
        "dataset_case_count": len(cases),
        "runs": {},
    }
    for run_name in run_names:
        rankings = {
            item.case_id: item.ranked_chunk_ids
            for item in predictions if item.run_name == run_name
        }
        report["runs"][run_name] = {
            "aggregate": _aggregate(cases, rankings, k=k),
            "slices": _slices(cases, rankings, k=k),
        }
    return report


def compare_runs(
    report: Mapping[str, Any],
    *,
    baseline_name: str,
    candidate_name: str,
    thresholds: EvaluationThresholds | None = None,
) -> dict[str, Any]:
    """Gate aggregate and matching language/risk/tenant slices against regressions."""
    thresholds = thresholds or EvaluationThresholds()
    runs = report.get("runs", {})
    if baseline_name not in runs or candidate_name not in runs:
        raise ValueError("baseline and candidate runs must both exist in report")
    limits = {
        "precision_at_k": thresholds.max_precision_drop,
        "recall_at_k": thresholds.max_recall_drop,
        "ndcg_at_k": thresholds.max_ndcg_drop,
    }

    def make_checks(baseline: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
        return {
            metric: {
                "baseline": baseline[metric],
                "candidate": candidate[metric],
                "delta": candidate[metric] - baseline[metric],
                "maximum_drop": limit,
                "passed": candidate[metric] - baseline[metric] >= -limit,
            }
            for metric, limit in limits.items()
        }

    baseline = runs[baseline_name]
    candidate = runs[candidate_name]
    aggregate_checks = make_checks(baseline["aggregate"], candidate["aggregate"])
    slice_checks: dict[str, Any] = {}
    for dimension, baseline_groups in baseline["slices"].items():
        candidate_groups = candidate["slices"].get(dimension, {})
        for group_name, baseline_metrics in baseline_groups.items():
            if group_name not in candidate_groups:
                slice_checks[f"{dimension}:{group_name}"] = {
                    "passed": False, "reason": "candidate report is missing a baseline slice"
                }
                continue
            checks = make_checks(baseline_metrics, candidate_groups[group_name])
            slice_checks[f"{dimension}:{group_name}"] = {
                "checks": checks,
                "passed": all(check["passed"] for check in checks.values()),
            }
    passed = (
        all(item["passed"] for item in aggregate_checks.values())
        and all(item["passed"] for item in slice_checks.values())
    )
    return {
        "baseline": baseline_name,
        "candidate": candidate_name,
        "thresholds": asdict(thresholds),
        "checks": aggregate_checks,
        "slice_checks": slice_checks,
        "passed": passed,
    }


def build_evaluation_report(
    cases: Sequence[EvaluationCase],
    predictions: Sequence[EvaluationPrediction],
    *,
    k: int = 5,
    baseline_name: str | None = None,
    candidate_name: str | None = None,
    thresholds: EvaluationThresholds | None = None,
) -> dict[str, Any]:
    """Evaluate runs and optionally add a release gate comparison."""
    report = evaluate_golden_runs(cases, predictions, k=k)
    if (baseline_name is None) != (candidate_name is None):
        raise ValueError("baseline_name and candidate_name must be provided together")
    if baseline_name is not None and candidate_name is not None:
        report["release_gate"] = compare_runs(
            report, baseline_name=baseline_name, candidate_name=candidate_name,
            thresholds=thresholds,
        )
    return report


def write_report(report: Mapping[str, Any], path: str | Path) -> None:
    """Write stable, machine-readable JSON for CI artifacts and experiment review."""
    Path(path).write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def evaluate_retrieval(
    hits: list[RetrievalHit], relevant_chunk_ids: set[str], *, k: int | None = None
) -> RetrievalMetrics:
    """Compatibility helper for evaluating a single in-memory retrieval result."""
    considered = hits[:k] if k is not None else hits
    found = {hit.chunk.chunk_id for hit in considered} & relevant_chunk_ids
    rank = next(
        (i for i, hit in enumerate(considered, 1) if hit.chunk.chunk_id in relevant_chunk_ids),
        None,
    )
    recall = len(found) / len(relevant_chunk_ids) if relevant_chunk_ids else 1.0
    return RetrievalMetrics(recall, 1 / rank if rank else 0.0, len(considered), len(found))


def evaluate_grounding(answer: str, evidence: list[Evidence]) -> dict[str, object]:
    """Compatibility helper for structural citation checks only."""
    report = validate_citations(answer, evidence)
    return {
        "valid_citation_structure": report.valid,
        "citation_coverage": 1.0 if report.has_citation else 0.0,
        "unknown_citations": list(report.unknown_citations),
        "note": report.reason,
    }

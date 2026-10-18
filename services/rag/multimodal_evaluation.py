"""Offline modality-sliced retrieval evaluation for multimodal RAG."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .evaluation import (
    EvaluationCase,
    EvaluationPrediction,
    MAX_CASES,
    _read_jsonl,
)
from .ranking import ranking_metrics

SUPPORTED_MODALITIES = frozenset({"text", "image", "audio", "video", "structured"})


def load_modality_map(path: str | Path) -> dict[str, str]:
    """Load strict JSONL mapping rows: {case_id, modality}."""
    result: dict[str, str] = {}
    for row in _read_jsonl(path):
        if set(row) != {"case_id", "modality"}:
            raise ValueError("modality row must contain only case_id and modality")
        case_id, modality = row["case_id"], row["modality"]
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError("case_id must be a non-empty string")
        if not isinstance(modality, str) or modality not in SUPPORTED_MODALITIES:
            raise ValueError(f"unsupported modality: {modality!r}")
        if case_id in result:
            raise ValueError(f"duplicate modality mapping for case_id: {case_id}")
        result[case_id] = modality
        if len(result) > MAX_CASES:
            raise ValueError("modality map contains too many cases")
    if not result:
        raise ValueError("modality map must contain at least one record")
    return result


def evaluate_multimodal_slices(
    cases: Sequence[EvaluationCase],
    predictions: Sequence[EvaluationPrediction],
    modalities: Mapping[str, str],
    *,
    k: int = 5,
) -> dict[str, Any]:
    """Evaluate ranked representation IDs overall and by input modality.

    Every query must have exactly one modality assignment. Missing run predictions
    count as empty retrievals; unknown cases and duplicate run/case predictions fail.
    """
    if not cases:
        raise ValueError("at least one evaluation case is required")
    if not 1 <= k <= 100:
        raise ValueError("k must be between 1 and 100")
    by_id = {case.case_id: case for case in cases}
    if len(by_id) != len(cases):
        raise ValueError("case IDs must be unique")
    if set(modalities) != set(by_id):
        missing = sorted(set(by_id) - set(modalities))
        extra = sorted(set(modalities) - set(by_id))
        raise ValueError(f"modality map must match dataset cases; missing={missing}, extra={extra}")
    invalid = {case_id: modality for case_id, modality in modalities.items()
               if not isinstance(modality, str) or modality not in SUPPORTED_MODALITIES}
    if invalid:
        raise ValueError(f"unsupported modality assignments: {invalid}")

    rankings: dict[str, dict[str, tuple[str, ...]]] = defaultdict(dict)
    for prediction in predictions:
        if prediction.case_id not in by_id:
            raise ValueError(f"prediction references unknown case ID: {prediction.case_id}")
        run = rankings[prediction.run_name]
        if prediction.case_id in run:
            raise ValueError(f"duplicate prediction for run/case: {(prediction.run_name, prediction.case_id)}")
        run[prediction.case_id] = prediction.ranked_chunk_ids
    if not rankings:
        raise ValueError("at least one named prediction run is required")

    def summarize(group: Sequence[EvaluationCase], run_rankings: Mapping[str, Sequence[str]]) -> dict[str, float | int]:
        rows = [
            ranking_metrics(run_rankings.get(case.case_id, ()), set(case.relevant_chunk_ids), k=k)
            for case in group
        ]
        metrics: dict[str, float | int] = {
            name: sum(row[name] for row in rows) / len(rows)
            for name in ("precision_at_k", "recall_at_k", "reciprocal_rank", "ndcg_at_k")
        }
        metrics["empty_result_rate"] = sum(
            not run_rankings.get(case.case_id, ()) for case in group
        ) / len(group)
        metrics["case_count"] = len(group)
        return metrics

    groups: dict[str, list[EvaluationCase]] = defaultdict(list)
    for case in cases:
        groups[modalities[case.case_id]].append(case)

    report: dict[str, Any] = {
        "schema_version": 1,
        "k": k,
        "dataset_case_count": len(cases),
        "modality_slices": {},
        "runs": {},
        "limitations": [
            "Modality labels are supplied by the dataset author; this evaluator does not inspect raw media.",
            "Metrics measure retrieval against provided relevance labels, not OCR/transcription fidelity.",
            "Synthetic fixtures do not establish real-world multimodal retrieval quality.",
        ],
    }
    report["modality_slices"] = {
        modality: {"case_count": len(group)} for modality, group in sorted(groups.items())
    }
    for run_name, run_rankings in sorted(rankings.items()):
        report["runs"][run_name] = {
            "aggregate": summarize(cases, run_rankings),
            "modalities": {
                modality: summarize(group, run_rankings)
                for modality, group in sorted(groups.items())
            },
        }
    return report

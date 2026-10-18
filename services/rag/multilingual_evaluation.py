"""Deterministic bootstrap uncertainty and paired multilingual RAG ablations.

This module evaluates existing ranked predictions; it does not label data or imply
that synthetic fixtures represent real-world language quality.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from .evaluation import EvaluationCase, EvaluationPrediction
from .ranking import ranking_metrics

_METRICS = ("precision_at_k", "recall_at_k", "reciprocal_rank", "ndcg_at_k")
_MAX_BOOTSTRAP_SAMPLES = 5000


def _percentile(sorted_values: list[float], probability: float) -> float:
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def _interval(values: list[float], confidence: float) -> dict[str, float]:
    ordered = sorted(values)
    tail = (1 - confidence) / 2
    return {
        "lower": _percentile(ordered, tail),
        "upper": _percentile(ordered, 1 - tail),
    }


def build_multilingual_ablation_report(
    cases: Sequence[EvaluationCase],
    predictions: Sequence[EvaluationPrediction],
    *,
    baseline_name: str,
    candidate_name: str,
    k: int = 5,
    bootstrap_samples: int = 1000,
    confidence: float = 0.95,
    seed: int = 37,
) -> dict[str, Any]:
    """Return per-language metrics and paired percentile-bootstrap intervals.

    Cases are the resampling unit. Baseline and candidate deltas use the same sampled
    cases, preserving pairing. Missing predictions count as empty rankings.
    """
    if not cases:
        raise ValueError("at least one evaluation case is required")
    if not baseline_name.strip() or not candidate_name.strip() or baseline_name == candidate_name:
        raise ValueError("baseline and candidate must be distinct non-empty run names")
    if not 1 <= k <= 100:
        raise ValueError("k must be between 1 and 100")
    if not 100 <= bootstrap_samples <= _MAX_BOOTSTRAP_SAMPLES:
        raise ValueError(f"bootstrap_samples must be between 100 and {_MAX_BOOTSTRAP_SAMPLES}")
    if not math.isfinite(confidence) or not 0.5 < confidence < 1:
        raise ValueError("confidence must be finite and between 0.5 and 1")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative integer")

    by_id = {case.case_id: case for case in cases}
    if len(by_id) != len(cases):
        raise ValueError("case IDs must be unique")
    prediction_map: dict[tuple[str, str], tuple[str, ...]] = {}
    for prediction in predictions:
        if prediction.case_id not in by_id:
            raise ValueError(f"prediction references unknown case ID: {prediction.case_id}")
        key = (prediction.run_name, prediction.case_id)
        if key in prediction_map:
            raise ValueError(f"duplicate prediction for run/case: {key}")
        prediction_map[key] = prediction.ranked_chunk_ids
    run_names = {name for name, _ in prediction_map}
    if baseline_name not in run_names or candidate_name not in run_names:
        raise ValueError("baseline and candidate runs must both exist")

    grouped: dict[str, list[EvaluationCase]] = defaultdict(list)
    for case in cases:
        grouped[case.language].append(case)

    def metrics_for(case: EvaluationCase, run_name: str) -> dict[str, float]:
        ranking = prediction_map.get((run_name, case.case_id), ())
        metrics = ranking_metrics(ranking, set(case.relevant_chunk_ids), k=k)
        metrics["empty_result_rate"] = 1.0 if not ranking else 0.0
        return metrics

    output: dict[str, Any] = {
        "schema_version": 1,
        "method": "paired_percentile_bootstrap",
        "confidence": confidence,
        "bootstrap_samples": bootstrap_samples,
        "seed": seed,
        "k": k,
        "baseline": baseline_name,
        "candidate": candidate_name,
        "language_slices": {},
        "limitations": [
            "Confidence intervals describe variation across the supplied cases, not population-wide guarantees.",
            "Results are only as representative as the relevance labels and query sample.",
            "Synthetic fixtures must not be described as human-reviewed language benchmarks.",
        ],
    }
    rng = random.Random(seed)
    for language, language_cases in sorted(grouped.items()):
        baseline_rows = [metrics_for(case, baseline_name) for case in language_cases]
        candidate_rows = [metrics_for(case, candidate_name) for case in language_cases]

        def mean(rows: list[dict[str, float]], metric: str) -> float:
            return sum(row[metric] for row in rows) / len(rows)

        metric_report: dict[str, Any] = {}
        for metric in (*_METRICS, "empty_result_rate"):
            baseline_value = mean(baseline_rows, metric)
            candidate_value = mean(candidate_rows, metric)
            baseline_samples: list[float] = []
            candidate_samples: list[float] = []
            delta_samples: list[float] = []
            count = len(language_cases)
            for _ in range(bootstrap_samples):
                sampled_indices = [rng.randrange(count) for _ in range(count)]
                base = sum(baseline_rows[i][metric] for i in sampled_indices) / count
                candidate = sum(candidate_rows[i][metric] for i in sampled_indices) / count
                baseline_samples.append(base)
                candidate_samples.append(candidate)
                delta_samples.append(candidate - base)
            metric_report[metric] = {
                "baseline": {
                    "value": baseline_value,
                    "confidence_interval": _interval(baseline_samples, confidence),
                },
                "candidate": {
                    "value": candidate_value,
                    "confidence_interval": _interval(candidate_samples, confidence),
                },
                "delta_candidate_minus_baseline": {
                    "value": candidate_value - baseline_value,
                    "confidence_interval": _interval(delta_samples, confidence),
                },
            }
        output["language_slices"][language] = {
            "case_count": len(language_cases),
            "metrics": metric_report,
        }
    return output

"""Composable ranking utilities for auditable hybrid retrieval experiments.

These helpers are provider- and database-independent. They operate on candidate IDs
and scores so experiments can compare ranking strategies without changing ingestion
or tenant authorization boundaries.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    candidate_id: str
    score: float

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate_id is required")
        if not math.isfinite(self.score):
            raise ValueError("score must be finite")


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]],
    *,
    weights: Sequence[float] | None = None,
    rank_constant: int = 60,
    top_k: int = 10,
) -> list[RankedCandidate]:
    """Fuse independent ranked lists using weighted reciprocal-rank fusion.

    Duplicate IDs within one list count only at their first occurrence. Missing
    candidates contribute zero to that list. The deterministic lexical ID tie-break
    makes offline evaluation reproducible.
    """
    if rank_constant < 0:
        raise ValueError("rank_constant must be non-negative")
    if not 1 <= top_k <= 1000:
        raise ValueError("top_k must be between 1 and 1000")
    if weights is None:
        effective_weights = [1.0] * len(rankings)
    else:
        effective_weights = list(weights)
        if len(effective_weights) != len(rankings):
            raise ValueError("weights must have one value per ranking")
        if any(not math.isfinite(weight) or weight < 0 for weight in effective_weights):
            raise ValueError("weights must be finite and non-negative")
    scores: dict[str, float] = {}
    for ranking, weight in zip(rankings, effective_weights):
        seen: set[str] = set()
        for position, candidate_id in enumerate(ranking, start=1):
            if not isinstance(candidate_id, str) or not candidate_id.strip():
                raise ValueError("ranking IDs must be non-empty strings")
            if candidate_id in seen:
                continue
            seen.add(candidate_id)
            scores[candidate_id] = scores.get(candidate_id, 0.0) + weight / (
                rank_constant + position
            )
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [RankedCandidate(candidate_id, score) for candidate_id, score in ordered[:top_k]]


def filter_candidates(
    candidates: Sequence[RankedCandidate],
    *,
    allowed_ids: set[str] | None = None,
    excluded_ids: set[str] | None = None,
    minimum_score: float | None = None,
) -> list[RankedCandidate]:
    """Apply explicit allow/deny and score filters while preserving input order."""
    if minimum_score is not None and not math.isfinite(minimum_score):
        raise ValueError("minimum_score must be finite")
    allowed = allowed_ids
    excluded = excluded_ids or set()
    return [
        candidate
        for candidate in candidates
        if (allowed is None or candidate.candidate_id in allowed)
        and candidate.candidate_id not in excluded
        and (minimum_score is None or candidate.score >= minimum_score)
    ]


def diversify_by_group(
    candidates: Sequence[RankedCandidate],
    groups: Mapping[str, str],
    *,
    per_group_limit: int = 2,
    top_k: int = 10,
) -> list[RankedCandidate]:
    """Limit near-duplicate source groups after ranking without changing scores.

    Candidates without a group mapping share no group and therefore remain eligible.
    The original candidate order is retained, and the function never introduces IDs
    that were not present in the ranked input.
    """
    if per_group_limit < 1:
        raise ValueError("per_group_limit must be positive")
    if not 1 <= top_k <= 1000:
        raise ValueError("top_k must be between 1 and 1000")
    counts: dict[str, int] = {}
    result: list[RankedCandidate] = []
    for candidate in candidates:
        group = groups.get(candidate.candidate_id)
        if group is not None:
            count = counts.get(group, 0)
            if count >= per_group_limit:
                continue
            counts[group] = count + 1
        result.append(candidate)
        if len(result) >= top_k:
            break
    return result


def ranking_metrics(
    ranked_ids: Sequence[str],
    relevant_ids: set[str],
    *,
    k: int = 10,
) -> dict[str, float]:
    """Compute precision@k, recall@k, reciprocal rank and NDCG@k for a binary set."""
    if not 1 <= k <= 1000:
        raise ValueError("k must be between 1 and 1000")
    if any(not isinstance(item, str) or not item.strip() for item in ranked_ids):
        raise ValueError("ranked IDs must be non-empty strings")
    top = list(ranked_ids[:k])
    relevant = [item in relevant_ids for item in top]
    hits = sum(relevant)
    precision = hits / k
    recall = hits / len(relevant_ids) if relevant_ids else 0.0
    reciprocal_rank = next(
        (1.0 / position for position, is_relevant in enumerate(relevant, 1) if is_relevant),
        0.0,
    )
    dcg = sum(1.0 / math.log2(position + 1) for position, is_relevant in enumerate(relevant, 1) if is_relevant)
    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(position + 1) for position in range(1, ideal_hits + 1))
    ndcg = dcg / idcg if idcg else 0.0
    return {
        "precision_at_k": precision,
        "recall_at_k": recall,
        "reciprocal_rank": reciprocal_rank,
        "ndcg_at_k": ndcg,
    }


def compare_ranking_runs(
    runs: Mapping[str, Mapping[str, Sequence[str]]],
    relevance: Mapping[str, set[str]],
    *,
    k: int = 10,
) -> dict[str, dict[str, float]]:
    """Compare named strategies over query-specific rankings and relevance labels."""
    if not runs:
        raise ValueError("at least one ranking run is required")
    if not relevance:
        raise ValueError("at least one relevance judgement is required")
    report: dict[str, dict[str, float]] = {}
    for name, query_runs in runs.items():
        if not name.strip():
            raise ValueError("run names must be non-empty")
        per_query = [
            ranking_metrics(query_runs.get(query_id, ()), relevant, k=k)
            for query_id, relevant in relevance.items()
        ]
        metric_names = per_query[0].keys()
        report[name] = {
            metric: sum(result[metric] for result in per_query) / len(per_query)
            for metric in metric_names
        }
    return report

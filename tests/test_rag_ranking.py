import pytest

from services.rag.ranking import (
    RankedCandidate,
    compare_ranking_runs,
    diversify_by_group,
    filter_candidates,
    ranking_metrics,
    reciprocal_rank_fusion,
)


def test_rrf_combines_ranked_lists_deterministically():
    result = reciprocal_rank_fusion(
        [["alpha", "shared", "beta"], ["shared", "beta", "alpha"]],
        rank_constant=0,
    )
    assert [item.candidate_id for item in result] == ["shared", "alpha", "beta"]
    assert result[0].score == pytest.approx(1.5)


def test_rrf_deduplicates_candidates_per_list():
    result = reciprocal_rank_fusion([["b", "b", "a"], ["a", "b"]], rank_constant=10)
    assert [item.candidate_id for item in result] == ["b", "a"]


@pytest.mark.parametrize("kwargs", [{"rank_constant": -1}, {"top_k": 0}, {"weights": [1.0]}])
def test_rrf_rejects_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"], ["b"]], **kwargs)


def test_rrf_rejects_invalid_weights_and_ids():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"]], weights=[float("nan")])
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[" "]])
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"]], weights=[-1.0])


def test_candidate_score_must_be_finite():
    with pytest.raises(ValueError):
        RankedCandidate("candidate", float("inf"))


def test_candidate_filters_preserve_order_and_apply_constraints():
    candidates = [RankedCandidate("a", 0.9), RankedCandidate("b", 0.7), RankedCandidate("c", 0.2)]
    filtered = filter_candidates(
        candidates, allowed_ids={"a", "b", "c"}, excluded_ids={"b"}, minimum_score=0.5
    )
    assert [item.candidate_id for item in filtered] == ["a"]


def test_filter_rejects_non_finite_threshold():
    with pytest.raises(ValueError):
        filter_candidates([RankedCandidate("a", 0.5)], minimum_score=float("nan"))


def test_diversification_caps_each_group_without_reordering():
    candidates = [
        RankedCandidate("a1", 0.99), RankedCandidate("a2", 0.98),
        RankedCandidate("b1", 0.97), RankedCandidate("a3", 0.96),
        RankedCandidate("c1", 0.95),
    ]
    result = diversify_by_group(
        candidates, {"a1": "doc-a", "a2": "doc-a", "a3": "doc-a", "b1": "doc-b"},
        per_group_limit=1, top_k=3,
    )
    assert [item.candidate_id for item in result] == ["a1", "b1", "c1"]


def test_diversification_validates_limits():
    with pytest.raises(ValueError):
        diversify_by_group([], {}, per_group_limit=0)
    with pytest.raises(ValueError):
        diversify_by_group([], {}, top_k=0)


def test_ranking_metrics_compute_precision_recall_mrr_and_ndcg():
    metrics = ranking_metrics(["x", "a", "b"], {"a", "b"}, k=3)
    assert metrics["precision_at_k"] == pytest.approx(2 / 3)
    assert metrics["recall_at_k"] == pytest.approx(1.0)
    assert metrics["reciprocal_rank"] == pytest.approx(0.5)
    assert metrics["ndcg_at_k"] == pytest.approx((0.6309297535714575 + 0.5) / 1.6309297535714575)


def test_ranking_metrics_handle_no_relevant_items():
    assert ranking_metrics(["a", "b"], set(), k=2) == {
        "precision_at_k": 0.0, "recall_at_k": 0.0,
        "reciprocal_rank": 0.0, "ndcg_at_k": 0.0,
    }


def test_ranking_metrics_validate_inputs():
    with pytest.raises(ValueError):
        ranking_metrics(["a"], {"a"}, k=0)
    with pytest.raises(ValueError):
        ranking_metrics([" "], {"a"})


def test_compare_ranking_runs_reports_mean_metrics():
    report = compare_ranking_runs(
        {
            "baseline": {"query-1": ["x", "a"], "query-2": ["a", "x"]},
            "candidate": {"query-1": ["a", "x"], "query-2": ["x", "a"]},
        },
        {"query-1": {"a"}, "query-2": {"x"}},
        k=2,
    )
    assert set(report) == {"baseline", "candidate"}
    assert report["baseline"]["precision_at_k"] == 0.5
    assert report["baseline"]["reciprocal_rank"] == 0.5
    assert report["candidate"]["reciprocal_rank"] == 1.0


def test_compare_ranking_runs_requires_inputs():
    with pytest.raises(ValueError):
        compare_ranking_runs({}, {"q": {"a"}})
    with pytest.raises(ValueError):
        compare_ranking_runs({"baseline": {"q": ["a"]}}, {})

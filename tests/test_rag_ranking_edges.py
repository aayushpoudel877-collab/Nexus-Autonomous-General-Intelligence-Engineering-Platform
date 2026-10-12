from services.rag.ranking import compare_ranking_runs, filter_candidates, ranking_metrics


def test_missing_query_ranking_counts_as_empty_result():
    report = compare_ranking_runs(
        {"sparse-run": {"q1": ["hit"]}},
        {"q1": {"hit"}, "q2": {"other"}},
        k=5,
    )
    assert report["sparse-run"]["reciprocal_rank"] == 0.5
    assert report["sparse-run"]["recall_at_k"] == 0.5


def test_metric_precision_uses_requested_k_even_for_short_result_lists():
    result = ranking_metrics(["hit"], {"hit"}, k=4)
    assert result["precision_at_k"] == 0.25
    assert result["recall_at_k"] == 1.0


def test_filtering_empty_candidate_list_is_stable():
    assert filter_candidates([], allowed_ids={"anything"}) == []

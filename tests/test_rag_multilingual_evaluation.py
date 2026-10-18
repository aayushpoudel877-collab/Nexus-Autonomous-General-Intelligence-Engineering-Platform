import json

import pytest

from services.rag.evaluation import EvaluationCase, EvaluationPrediction
from services.rag.multilingual_evaluation import build_multilingual_ablation_report


def _cases():
    return [
        EvaluationCase("en-1", "tenant-a", "alpha", ("a",), "en"),
        EvaluationCase("en-2", "tenant-a", "beta", ("b",), "en"),
        EvaluationCase("ne-1", "tenant-b", "नेपाल", ("n",), "ne"),
        EvaluationCase("ne-2", "tenant-b", "काठमाडौं", ("k",), "ne"),
    ]


def _predictions():
    return [
        EvaluationPrediction("baseline", "en-1", ("a",)),
        EvaluationPrediction("baseline", "en-2", ("wrong",)),
        EvaluationPrediction("baseline", "ne-1", ("wrong",)),
        EvaluationPrediction("baseline", "ne-2", ("k",)),
        EvaluationPrediction("ngram-04", "en-1", ("a",)),
        EvaluationPrediction("ngram-04", "en-2", ("b",)),
        EvaluationPrediction("ngram-04", "ne-1", ("n",)),
        EvaluationPrediction("ngram-04", "ne-2", ("k",)),
    ]


def test_multilingual_ablation_reports_language_slices_and_paired_intervals():
    report = build_multilingual_ablation_report(
        _cases(), _predictions(), baseline_name="baseline",
        candidate_name="ngram-04", k=1, bootstrap_samples=200, seed=123,
    )
    assert report["method"] == "paired_percentile_bootstrap"
    assert report["language_slices"]["ne"]["case_count"] == 2
    recall = report["language_slices"]["ne"]["metrics"]["recall_at_k"]
    assert recall["candidate"]["value"] == 1.0
    assert recall["delta_candidate_minus_baseline"]["value"] == 0.5
    assert 0 <= recall["delta_candidate_minus_baseline"]["confidence_interval"]["lower"] <= 0.5
    assert recall["delta_candidate_minus_baseline"]["confidence_interval"]["upper"] == 1.0


def test_multilingual_ablation_is_reproducible_for_same_seed():
    kwargs = dict(
        cases=_cases(), predictions=_predictions(), baseline_name="baseline",
        candidate_name="ngram-04", k=2, bootstrap_samples=200, seed=99,
    )
    first = build_multilingual_ablation_report(**kwargs)
    second = build_multilingual_ablation_report(**kwargs)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


@pytest.mark.parametrize("samples", [0, 99, 5001])
def test_bootstrap_sample_count_is_bounded(samples):
    with pytest.raises(ValueError, match="bootstrap_samples"):
        build_multilingual_ablation_report(
            _cases(), _predictions(), baseline_name="baseline",
            candidate_name="ngram-04", bootstrap_samples=samples,
        )


def test_ablation_rejects_duplicate_predictions_and_missing_runs():
    duplicate = _predictions() + [_predictions()[0]]
    with pytest.raises(ValueError, match="duplicate prediction"):
        build_multilingual_ablation_report(
            _cases(), duplicate, baseline_name="baseline", candidate_name="ngram-04",
        )
    with pytest.raises(ValueError, match="both exist"):
        build_multilingual_ablation_report(
            _cases(), _predictions(), baseline_name="baseline", candidate_name="missing",
        )


def test_ablation_rejects_unknown_cases_and_invalid_confidence():
    with pytest.raises(ValueError, match="unknown case"):
        build_multilingual_ablation_report(
            _cases(), [EvaluationPrediction("baseline", "unknown", ("a",))],
            baseline_name="baseline", candidate_name="candidate",
        )
    with pytest.raises(ValueError, match="confidence"):
        build_multilingual_ablation_report(
            _cases(), _predictions(), baseline_name="baseline",
            candidate_name="ngram-04", confidence=1.0,
        )

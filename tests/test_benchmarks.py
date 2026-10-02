from uuid import uuid4

import pytest
from pydantic import ValidationError

from services.api.app.schemas.benchmarks import BenchmarkComparisonCreate
from services.api.app.services.benchmarks import compare_metrics


def test_comparison_passes_when_directional_thresholds_are_met():
    passed, deltas, issues = compare_metrics(
        {"accuracy": 0.8, "loss": 0.4}, {"accuracy": 0.9, "loss": 0.3},
        {"accuracy": {"direction": "maximize", "minimum_improvement": 0.05},
         "loss": {"direction": "minimize", "minimum_improvement": 0.05}},
    )
    assert passed is True
    assert deltas["accuracy"] == pytest.approx(0.1)
    assert deltas["loss"] == pytest.approx(-0.1)
    assert issues == []


def test_comparison_flags_regression_and_missing_metrics():
    passed, deltas, issues = compare_metrics(
        {"accuracy": 0.9}, {"accuracy": 0.85},
        {"accuracy": {"direction": "maximize", "minimum_improvement": 0}},
    )
    assert passed is False
    assert deltas["accuracy"] == pytest.approx(-0.05)
    assert "below required" in issues[0]
    passed, _, issues = compare_metrics({}, {}, {"loss": {"direction": "minimize"}})
    assert passed is False
    assert "finite numeric" in issues[0]


def test_schema_rejects_same_model_and_missing_criterion_metrics():
    same = uuid4()
    with pytest.raises(ValidationError, match="different models"):
        BenchmarkComparisonCreate(baseline_model_id=same, candidate_model_id=same,
            baseline_metrics={"accuracy": 0.8}, candidate_metrics={"accuracy": 0.9},
            criteria={"accuracy": {"direction": "maximize"}})
    with pytest.raises(ValidationError, match="missing"):
        BenchmarkComparisonCreate(baseline_model_id=uuid4(), candidate_model_id=uuid4(),
            baseline_metrics={"accuracy": 0.8}, candidate_metrics={"loss": 0.2},
            criteria={"accuracy": {"direction": "maximize"}})


def test_schema_rejects_non_finite_and_boolean_metrics():
    for value in (float("nan"), True):
        with pytest.raises(ValidationError, match="finite numbers"):
            BenchmarkComparisonCreate(baseline_model_id=uuid4(), candidate_model_id=uuid4(),
                baseline_metrics={"accuracy": value}, candidate_metrics={"accuracy": 0.9},
                criteria={"accuracy": {"direction": "maximize"}})

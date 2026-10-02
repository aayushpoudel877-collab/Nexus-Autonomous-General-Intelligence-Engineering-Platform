import pytest
from pydantic import ValidationError

from services.api.app.schemas.ml_lifecycle import (
    ModelEvaluationCreate,
    ModelEvaluationUpdate,
    RegisteredModelCreate,
    RegisteredModelUpdate,
    TrainingRunCreate,
    TrainingRunUpdate,
)
from services.api.app.services.ml_lifecycle import (
    ensure_evaluation_transition,
    evaluation_criteria_met,
    evaluate_metrics,
    ensure_model_transition,
    ensure_run_transition,
)


def test_training_run_schema_has_bounded_parameters():
    run = TrainingRunCreate(name="Baseline", parameters={"seed": 7, "rate": 0.02})
    assert run.algorithm == "baseline"
    assert run.parameters["seed"] == 7


def test_training_run_update_rejects_empty_payload():
    with pytest.raises(ValidationError, match="At least one training run field"):
        TrainingRunUpdate()
    with pytest.raises(ValidationError, match="Update fields cannot be null"):
        TrainingRunUpdate(status=None)


def test_training_run_lifecycle_requires_running_before_completion():
    with pytest.raises(ValueError, match="Cannot change training run status"):
        ensure_run_transition("queued", "succeeded")
    ensure_run_transition("queued", "running")
    ensure_run_transition("running", "succeeded")
    ensure_run_transition("running", "failed")


def test_training_run_terminal_states_cannot_reopen():
    with pytest.raises(ValueError):
        ensure_run_transition("succeeded", "running")


def test_model_requires_exactly_one_successful_source_reference():
    with pytest.raises(ValidationError, match="must reference a training run or experiment"):
        RegisteredModelCreate(name="Classifier", version="1.0")
    with pytest.raises(ValidationError, match="Choose one model source"):
        RegisteredModelCreate(
            name="Classifier",
            version="1.0",
            source_training_run_id="d9428888-122b-4f35-a8a8-5e9a9a4e82aa",
            source_experiment_id="e9428888-122b-4f35-a8a8-5e9a9a4e82aa",
        )


def test_model_approval_requires_human_note_field():
    with pytest.raises(ValidationError, match="At least one model field"):
        RegisteredModelUpdate()
    with pytest.raises(ValidationError, match="Update fields cannot be null"):
        RegisteredModelUpdate(approval_note=None)
    assert RegisteredModelUpdate(status="approved").status == "approved"


def test_model_lifecycle_is_one_way_and_reviewable():
    ensure_model_transition("candidate", "validated")
    ensure_model_transition("validated", "approved")
    ensure_model_transition("approved", "archived")
    with pytest.raises(ValueError):
        ensure_model_transition("candidate", "approved")
    with pytest.raises(ValueError):
        ensure_model_transition("archived", "approved")


def test_evaluation_schema_and_lifecycle():
    evaluation = ModelEvaluationCreate(
        evaluator="held-out validation",
        metrics={"accuracy": 0.95, "loss": 0.08},
        criteria={"accuracy": {"min": 0.9}, "loss": {"max": 0.1}},
    )
    assert evaluation.evaluator == "held-out validation"
    assert evaluation.criteria["accuracy"].min == 0.9
    with pytest.raises(ValidationError, match="At least one evaluation field"):
        ModelEvaluationUpdate()
    with pytest.raises(ValidationError, match="Update fields cannot be null"):
        ModelEvaluationUpdate(summary=None)
    ensure_evaluation_transition("queued", "running")
    ensure_evaluation_transition("running", "passed")
    with pytest.raises(ValueError):
        ensure_evaluation_transition("passed", "running")


def test_evaluation_pass_requires_numeric_metrics_and_explicit_thresholds():
    passed, issues = evaluation_criteria_met(
        {"accuracy": 0.95, "loss": 0.08},
        {"accuracy": {"min": 0.9}, "loss": {"max": 0.1}},
    )
    assert passed is True
    assert issues == []

    passed, issues = evaluation_criteria_met(
        {"accuracy": 0.84}, {"accuracy": {"min": 0.9}}
    )
    assert passed is False
    assert "below its minimum" in issues[0]

    passed, issues = evaluation_criteria_met({}, {"accuracy": {"min": 0.9}})
    assert passed is False
    assert "finite numeric result" in issues[0]

    passed, issues = evaluation_criteria_met({"accuracy": 1.0}, {})
    assert passed is False
    assert "criterion is required" in issues[0]


def test_evaluation_criteria_require_valid_bounds():
    with pytest.raises(ValidationError, match="must define min and/or max"):
        ModelEvaluationCreate(evaluator="validation", criteria={"accuracy": {}})
    with pytest.raises(ValidationError, match="cannot exceed max"):
        ModelEvaluationCreate(
            evaluator="validation", criteria={"accuracy": {"min": 0.95, "max": 0.9}}
        )


def test_automated_evaluator_returns_terminal_status_and_explanations():
    status, issues = evaluate_metrics(
        {"accuracy": 0.96, "loss": 0.08},
        {"accuracy": {"min": 0.9}, "loss": {"max": 0.1}},
    )
    assert status == "passed"
    assert issues == []
    status, issues = evaluate_metrics(
        {"accuracy": 0.8}, {"accuracy": {"min": 0.9}},
    )
    assert status == "failed"
    assert "below its minimum" in issues[0]

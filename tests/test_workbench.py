import pytest
from pydantic import ValidationError

from services.api.app.schemas.workbench import (
    DatasetCreate,
    ExperimentCreate,
    ExperimentUpdate,
    ProjectCreate,
)


def test_project_schema_accepts_supported_task_type():
    project = ProjectCreate(name="Image quality", task_type="computer_vision")
    assert project.task_type == "computer_vision"


def test_project_schema_rejects_unknown_task_type():
    with pytest.raises(ValidationError):
        ProjectCreate(name="Unknown task", task_type="make_everything")


def test_dataset_schema_rejects_negative_row_count():
    with pytest.raises(ValidationError):
        DatasetCreate(name="Training set", row_count=-1)


def test_experiment_defaults_are_reproducible():
    experiment = ExperimentCreate(
        name="Baseline run",
        parameters={"seed": 42, "learning_rate": 0.01},
    )
    assert experiment.algorithm == "baseline"
    assert experiment.dataset_id is None
    assert experiment.parameters["seed"] == 42


def test_experiment_status_is_constrained():
    with pytest.raises(ValidationError):
        ExperimentUpdate(status="mystery")
    assert ExperimentUpdate(status="succeeded").status == "succeeded"


def test_experiment_update_rejects_empty_payload():
    with pytest.raises(ValidationError, match="At least one experiment field"):
        ExperimentUpdate()


def test_experiment_lifecycle_allows_forward_progress():
    from services.api.app.services.workbench import ensure_status_transition

    ensure_status_transition("planned", "queued")
    ensure_status_transition("queued", "running")
    ensure_status_transition("running", "succeeded")
    ensure_status_transition("running", "failed")


def test_experiment_lifecycle_rejects_terminal_reopen():
    from services.api.app.services.workbench import ensure_status_transition

    with pytest.raises(ValueError, match="Cannot change experiment status"):
        ensure_status_transition("succeeded", "running")

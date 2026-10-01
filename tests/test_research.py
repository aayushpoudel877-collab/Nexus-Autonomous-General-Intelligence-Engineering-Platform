import pytest
from pydantic import ValidationError

from services.api.app.schemas.research import (
    ResearchPlanCreate,
    ResearchTaskCreate,
    ResearchTaskUpdate,
)
from services.api.app.services.research import (
    dependencies_succeeded,
    ensure_task_transition,
    validate_dependencies,
)


def test_research_plan_requires_a_specific_goal():
    with pytest.raises(ValidationError):
        ResearchPlanCreate(title="Study", goal="short")


def test_research_task_schema_limits_task_types():
    with pytest.raises(ValidationError):
        ResearchTaskCreate(title="Do work", task_type="untrusted-command")


def test_dependencies_must_exist_in_same_plan():
    with pytest.raises(ValueError, match="same research plan"):
        validate_dependencies(["task-a"], {"task-b"})


def test_dependency_list_cannot_repeat_ids():
    with pytest.raises(ValueError, match="more than once"):
        validate_dependencies(["task-a", "task-a"], {"task-a"})


def test_dependency_readiness_requires_every_dependency_to_succeed():
    assert dependencies_succeeded(["succeeded", "succeeded"])
    assert not dependencies_succeeded(["succeeded", "running"])
    assert not dependencies_succeeded([]) is False


def test_task_lifecycle_blocks_skipping_required_states():
    with pytest.raises(ValueError, match="Cannot change research task status"):
        ensure_task_transition("planned", "succeeded")
    ensure_task_transition("planned", "ready")
    ensure_task_transition("ready", "running")


def test_task_update_status_is_validated():
    with pytest.raises(ValidationError):
        ResearchTaskUpdate(status="finished-ish")

import pytest

from services.api.app.services.workflow_recovery import build_recovery_plan


def test_drift_adds_inspection_before_node_recommendations():
    plan = build_recovery_plan(
        run_status="failed",
        node_statuses={"training": "failed"},
        replay_drifted=True,
    )
    assert [item.action for item in plan.actions] == ["inspect", "retry_node"]
    assert plan.actions[1].node_key == "training"
    assert plan.automatic_mutation_allowed is False


def test_retry_waiting_uses_normal_scheduler_not_immediate_retry():
    plan = build_recovery_plan(
        run_status="running",
        node_statuses={"research": "retry_waiting"},
        replay_drifted=False,
    )
    assert plan.actions[0].action == "resume_run"
    assert "due time" in plan.actions[0].reason


def test_terminal_run_is_never_reopened_by_plan():
    plan = build_recovery_plan(
        run_status="succeeded",
        node_statuses={"done": "succeeded"},
        replay_drifted=False,
    )
    assert [item.action for item in plan.actions] == ["manual_review"]
    assert plan.automatic_mutation_allowed is False


def test_plan_is_bounded_and_rejects_invalid_limit():
    with pytest.raises(ValueError):
        build_recovery_plan(
            run_status="failed",
            node_statuses={},
            replay_drifted=False,
            max_actions=0,
        )
    plan = build_recovery_plan(
        run_status="failed",
        node_statuses={f"n{i}": "failed" for i in range(40)},
        replay_drifted=False,
        max_actions=3,
    )
    assert len(plan.actions) == 3

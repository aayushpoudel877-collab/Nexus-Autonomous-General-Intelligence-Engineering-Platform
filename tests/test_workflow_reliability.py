from datetime import datetime, timezone

import pytest

from services.api.app.schemas.workflow import WorkflowNodeCreate
from services.api.app.services.workflow import ensure_node_run_transition
from services.api.app.services.workflow_reliability import (
    next_retry_at,
    replay_fingerprint,
    retry_allowed,
    retry_delay_seconds,
    validate_retry_policy,
)


def test_retry_policy_defaults_are_bounded():
    assert validate_retry_policy({}) == {
        "max_attempts": 1,
        "backoff_seconds": 5,
        "retryable_errors": [],
    }


def test_retry_policy_rejects_unbounded_values():
    with pytest.raises(ValueError):
        validate_retry_policy({"max_attempts": 6})
    with pytest.raises(ValueError):
        validate_retry_policy({"backoff_seconds": 301})


def test_retry_policy_requires_explicit_error_markers():
    policy = {"max_attempts": 3, "backoff_seconds": 2, "retryable_errors": ["timeout", "temporary"]}
    assert retry_allowed(policy, 1, "temporary network failure")
    assert not retry_allowed(policy, 1, "permanent validation failure")
    assert not retry_allowed(policy, 3, "temporary network failure")


def test_retry_backoff_is_exponential_and_bounded():
    policy = {"max_attempts": 5, "backoff_seconds": 5, "retryable_errors": ["timeout"]}
    assert retry_delay_seconds(policy, 1) == 5
    assert retry_delay_seconds(policy, 2) == 10
    assert retry_delay_seconds(policy, 4) == 40
    assert retry_delay_seconds(policy, 99) == 300


def test_next_retry_at_preserves_timezone():
    now = datetime(2026, 10, 7, 3, 0, tzinfo=timezone.utc)
    assert next_retry_at(now, {"max_attempts": 3, "backoff_seconds": 10, "retryable_errors": ["timeout"]}, 2).isoformat() == "2026-10-07T03:00:20+00:00"


def test_replay_fingerprint_is_deterministic_and_input_sensitive():
    a = replay_fingerprint("run", "node", 1, {"x": 1, "y": 2})
    b = replay_fingerprint("run", "node", 1, {"y": 2, "x": 1})
    c = replay_fingerprint("run", "node", 2, {"x": 1, "y": 2})
    assert a == b
    assert a != c
    assert len(a) == 64


def test_retry_waiting_is_a_fail_closed_lifecycle_state():
    ensure_node_run_transition("running", "retry_waiting")
    ensure_node_run_transition("retry_waiting", "pending")
    with pytest.raises(ValueError):
        ensure_node_run_transition("succeeded", "retry_waiting")


def test_schema_accepts_retry_policy_without_credentials():
    node = WorkflowNodeCreate(
        node_key="execute",
        title="Execute",
        node_type="execution",
        config={
            "execution_request_id": "00000000-0000-0000-0000-000000000001",
            "retry": {"max_attempts": 3, "backoff_seconds": 10, "retryable_errors": ["timeout"]},
        },
    )
    assert node.config["retry"]["max_attempts"] == 3


def test_schema_rejects_unknown_retry_fields():
    with pytest.raises(ValueError):
        WorkflowNodeCreate(
            node_key="execute",
            title="Execute",
            node_type="execution",
            config={
                "execution_request_id": "00000000-0000-0000-0000-000000000001",
                "retry": {"forever": True},
            },
        )

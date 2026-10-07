import hashlib
from types import SimpleNamespace
from uuid import uuid4

import pytest

from services.api.app.schemas.workflow import WorkflowReplayRead
from services.api.app.services.workflow_replay import _canonical_event


def test_replay_event_canonicalization_is_deterministic():
    event = SimpleNamespace(
        sequence=4,
        event_type="workflow.tick",
        from_status=None,
        to_status="running",
        attempt=1,
        payload_json={"node_statuses": {"b": "pending", "a": "succeeded"}},
        actor="orchestrator",
    )
    first = _canonical_event(event)
    second = _canonical_event(event)
    assert first == second
    assert hashlib.sha256(first).hexdigest()


def test_replay_response_contract():
    payload = WorkflowReplayRead(
        run_id=uuid4(),
        event_count=2,
        replay_checksum="a" * 64,
        projected_status="running",
        projected_nodes=[{"node_key": "a", "status": "succeeded"}],
        drifted=False,
    )
    assert payload.event_count == 2
    assert payload.projected_nodes[0].node_key == "a"


def test_replay_checksum_changes_when_event_changes():
    base = dict(
        sequence=1,
        event_type="workflow.tick",
        from_status=None,
        to_status="running",
        attempt=0,
        payload_json={"node_statuses": {"a": "pending"}},
        actor="orchestrator",
    )
    changed = SimpleNamespace(**{**base, "to_status": "failed"})
    original = _canonical_event(SimpleNamespace(**base))
    assert _canonical_event(changed) != original


def test_replay_schema_rejects_missing_checksum():
    with pytest.raises(Exception):
        WorkflowReplayRead(
            run_id=uuid4(),
            event_count=1,
            projected_status="running",
            projected_nodes=[],
            drifted=False,
        )

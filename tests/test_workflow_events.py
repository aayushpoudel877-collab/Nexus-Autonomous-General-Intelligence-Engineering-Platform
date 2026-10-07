import pytest

from services.api.app.db.base import Base
from services.api.app.models.workflow_event import WorkflowEvent
from services.api.app.schemas.workflow import WorkflowEventRead
from services.api.app.services.workflow_events import _validate_payload


def test_workflow_event_table_is_registered():
    assert "workflow_events" in Base.metadata.tables


def test_workflow_event_payload_rejects_credentials():
    with pytest.raises(ValueError, match="credential"):
        _validate_payload({"api_token": "do-not-store"})


def test_workflow_event_payload_is_bounded():
    with pytest.raises(ValueError, match="too large"):
        _validate_payload({"result": "x" * 20_000})


def test_workflow_event_contract_is_typed():
    fields = WorkflowEventRead.model_fields
    assert {"sequence", "event_type", "payload_json", "actor"} <= set(fields)


def test_workflow_event_indexes_are_present():
    names = {index.name for index in WorkflowEvent.__table__.indexes}
    assert "ix_workflow_events_run_sequence" in names
    assert "ix_workflow_events_run_created" in names
    assert "ix_workflow_events_node_created" in names


def test_workflow_event_route_is_registered():
    from services.api.app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/workflows/{workflow_id}/runs/{run_id}/events" in paths

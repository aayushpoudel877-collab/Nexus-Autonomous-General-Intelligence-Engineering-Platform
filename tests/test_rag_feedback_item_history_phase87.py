from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from services.api.app.main import app
from services.api.app.routes import rag_operator


def _dependency_calls(dependant):
    calls = {getattr(dependency.call, "__name__", "") for dependency in dependant.dependencies}
    for dependency in dependant.dependencies:
        calls.update(_dependency_calls(dependency))
    return calls


def _result(rows):
    result = MagicMock()
    result.all.return_value = rows
    return result


def test_feedback_history_route_is_registered_and_role_gated():
    assert "/api/v1/rag/operator/feedback/{feedback_id}/history" in app.openapi()["paths"]
    route = next(
        route for route in rag_operator.router.routes
        if isinstance(route, APIRoute) and route.path.endswith("/feedback/{feedback_id}/history")
    )
    assert "get_current_user" in _dependency_calls(route.dependant)


@pytest.mark.asyncio
async def test_feedback_history_returns_tenant_scoped_timeline_without_actor_details(monkeypatch):
    organization_id = uuid4()
    feedback_id = uuid4()
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=organization_id)
    feedback = SimpleNamespace(status="resolved")
    session = AsyncMock()
    submitted_at = datetime(2026, 11, 1, tzinfo=timezone.utc)
    triaged_at = datetime(2026, 11, 2, tzinfo=timezone.utc)
    resolved_at = datetime(2026, 11, 3, tzinfo=timezone.utc)
    session.scalar.return_value = feedback
    session.execute.return_value = _result([
        ("rag.feedback.created", {"rating": "unhelpful"}, submitted_at),
        ("rag.feedback.status_updated", {"status": "triaged"}, triaged_at),
        ("rag.feedback.status_updated", {"status": "resolved"}, resolved_at),
        ("rag.feedback.status_updated", {"status": "unknown"}, resolved_at),
    ])

    async def membership_for_user(_user, _session):
        return membership

    monkeypatch.setattr(rag_operator, "get_membership", membership_for_user)
    response = await rag_operator.feedback_history(
        feedback_id=feedback_id, user=user, db=session
    )

    assert response["current_status"] == "resolved"
    assert response["events"] == [
        {"event": "submitted", "created_at": submitted_at},
        {"event": "triaged", "created_at": triaged_at},
        {"event": "resolved", "created_at": resolved_at},
    ]
    assert "actor identifiers" in response["privacy"]
    assert "actor_user_id" not in str(response)

    feedback_lookup = session.scalar.await_args.args[0]
    assert "rag_feedback.organization_id" in str(feedback_lookup)
    assert feedback_id in feedback_lookup.compile().params.values()
    audit_lookup = session.execute.await_args.args[0]
    sql = str(audit_lookup)
    assert "audit_events.organization_id" in sql
    assert "audit_events.resource_id" in sql
    assert "audit_events.action" in sql
    params = audit_lookup.compile().params
    assert organization_id in params.values()
    assert str(feedback_id) in params.values()


@pytest.mark.asyncio
async def test_feedback_history_hides_feedback_from_other_organizations(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=uuid4())
    session = AsyncMock()
    session.scalar.return_value = None

    async def membership_for_user(_user, _session):
        return membership

    monkeypatch.setattr(rag_operator, "get_membership", membership_for_user)
    with pytest.raises(HTTPException) as error:
        await rag_operator.feedback_history(
            feedback_id=uuid4(), user=user, db=session
        )

    assert error.value.status_code == 404
    session.execute.assert_not_awaited()

from datetime import datetime, time, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
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


def test_feedback_lifecycle_route_is_bounded_and_role_gated():
    operation = app.openapi()["paths"]["/api/v1/rag/operator/feedback/lifecycle-trend"]["get"]
    days = next(parameter for parameter in operation["parameters"] if parameter["name"] == "days")
    assert days["schema"]["minimum"] == 7
    assert days["schema"]["maximum"] == 90
    route = next(
        route for route in rag_operator.router.routes
        if isinstance(route, APIRoute) and route.path.endswith("/feedback/lifecycle-trend")
    )
    assert "get_current_user" in _dependency_calls(route.dependant)


@pytest.mark.asyncio
async def test_feedback_lifecycle_trend_aggregates_tenant_audit_actions(monkeypatch):
    organization_id = uuid4()
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=organization_id)
    session = AsyncMock()
    today = datetime.now(timezone.utc).date()
    bucket_at = datetime.combine(today, time.min, tzinfo=timezone.utc)
    session.execute.return_value = _result([
        (bucket_at, "created", 4),
        (bucket_at, "triaged", 2),
        (bucket_at, "resolved", 1),
        (bucket_at, "ignored", 1),
    ])

    async def membership_for_user(_user, _session):
        return membership

    monkeypatch.setattr(rag_operator, "get_membership", membership_for_user)
    response = await rag_operator.feedback_lifecycle_trend(days=7, user=user, db=session)

    assert response["days"] == 7
    assert response["timezone"] == "UTC"
    assert response["totals"] == {
        "created": 4,
        "triaged": 2,
        "resolved": 1,
        "ignored": 1,
        "total_actions": 8,
    }
    assert len(response["series"]) == 7
    assert response["series"][-1] == {
        "date": today.isoformat(),
        "created": 4,
        "triaged": 2,
        "resolved": 1,
        "ignored": 1,
        "total_actions": 8,
    }
    assert response["series"][0]["total_actions"] == 0
    assert "not unique feedback records" in response["interpretation"]
    assert "resource IDs" in response["privacy"]

    statement = session.execute.await_args.args[0]
    sql = str(statement)
    assert "audit_events.organization_id" in sql
    assert "audit_events.resource_type" in sql
    assert "audit_events.created_at" in sql
    params = statement.compile().params
    assert organization_id in params.values()
    assert "rag_feedback" in params.values()
    assert ["rag.feedback.created", "rag.feedback.status_updated"] in params.values()


@pytest.mark.asyncio
async def test_feedback_lifecycle_trend_empty_window_returns_zero_filled_days(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=uuid4())
    session = AsyncMock()
    session.execute.return_value = _result([])

    async def membership_for_user(_user, _session):
        return membership

    monkeypatch.setattr(rag_operator, "get_membership", membership_for_user)
    response = await rag_operator.feedback_lifecycle_trend(days=14, user=user, db=session)

    assert response["totals"]["total_actions"] == 0
    assert len(response["series"]) == 14
    assert all(day["total_actions"] == 0 for day in response["series"])

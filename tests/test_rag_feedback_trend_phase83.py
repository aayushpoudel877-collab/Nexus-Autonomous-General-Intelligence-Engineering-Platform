from datetime import datetime, time, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
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


def test_feedback_trend_route_is_registered_with_bounded_days_and_authentication():
    operation = app.openapi()["paths"]["/api/v1/rag/operator/feedback/trend"]["get"]
    days = next(parameter for parameter in operation["parameters"] if parameter["name"] == "days")
    assert days["schema"]["minimum"] == 7
    assert days["schema"]["maximum"] == 90
    route = next(
        route for route in rag_operator.router.routes
        if isinstance(route, APIRoute) and route.path.endswith("/feedback/trend")
    )
    assert "get_current_user" in _dependency_calls(route.dependant)


@pytest.mark.asyncio
async def test_feedback_trend_returns_zero_filled_utc_days_and_tenant_scoped_counts(monkeypatch):
    organization_id = uuid4()
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=organization_id)
    session = AsyncMock()
    today = datetime.now(timezone.utc).date()
    bucket_at = datetime.combine(today, time.min, tzinfo=timezone.utc)
    session.execute.return_value.all.return_value = [
        (bucket_at, "helpful", 2),
        (bucket_at, "unhelpful", 1),
    ]

    async def membership_for_user(_user, _session):
        return membership

    monkeypatch.setattr(rag_operator, "get_membership", membership_for_user)
    response = await rag_operator.feedback_trend(days=7, user=user, db=session)

    assert response["days"] == 7
    assert response["timezone"] == "UTC"
    assert response["total"] == 3
    assert len(response["series"]) == 7
    assert response["series"][-1] == {
        "date": today.isoformat(),
        "helpful": 2,
        "unhelpful": 1,
        "total": 3,
    }
    assert response["series"][0]["total"] == 0
    statement = session.execute.await_args.args[0]
    sql = str(statement)
    assert "rag_feedback.organization_id" in sql
    assert str(organization_id) not in sql


@pytest.mark.asyncio
async def test_feedback_trend_empty_period_returns_zero_counts(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=uuid4())
    session = AsyncMock()
    session.execute.return_value.all.return_value = []

    async def membership_for_user(_user, _session):
        return membership

    monkeypatch.setattr(rag_operator, "get_membership", membership_for_user)
    response = await rag_operator.feedback_trend(days=14, user=user, db=session)

    assert response["days"] == 14
    assert response["total"] == 0
    assert len(response["series"]) == 14
    assert all(day["total"] == 0 for day in response["series"])
    assert "raw queries" in response["privacy"]

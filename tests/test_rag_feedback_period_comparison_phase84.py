from datetime import date\nfrom types import SimpleNamespace
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


def test_feedback_comparison_route_is_registered_with_bounded_days_and_authentication():
    operation = app.openapi()["paths"]["/api/v1/rag/operator/feedback/compare"]["get"]
    days = next(parameter for parameter in operation["parameters"] if parameter["name"] == "days")
    assert days["schema"]["minimum"] == 7
    assert days["schema"]["maximum"] == 90
    route = next(
        route for route in rag_operator.router.routes
        if isinstance(route, APIRoute) and route.path.endswith("/feedback/compare")
    )
    assert "get_current_user" in _dependency_calls(route.dependant)


@pytest.mark.asyncio
async def test_feedback_comparison_returns_adjacent_period_aggregates_and_changes(monkeypatch):
    organization_id = uuid4()
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=organization_id)
    session = AsyncMock()
    session.execute.side_effect = [
        _result([("helpful", 6), ("unhelpful", 4)]),
        _result([("helpful", 4), ("unhelpful", 6)]),
    ]

    async def membership_for_user(_user, _session):
        return membership

    monkeypatch.setattr(rag_operator, "get_membership", membership_for_user)
    response = await rag_operator.feedback_period_comparison(days=7, user=user, db=session)

    assert response["days"] == 7
    assert response["timezone"] == "UTC"
    assert response["current"]["total"] == 10
    assert response["current"]["helpful_rate_percent"] == 60.0
    assert response["previous"]["total"] == 10
    assert response["previous"]["helpful_rate_percent"] == 40.0
    assert response["change"] == {
        "total": {"absolute": 0, "percent": 0.0},
        "helpful": {"absolute": 2, "percent": 50.0},
        "unhelpful": {"absolute": -2, "percent": -33.3},
        "helpful_rate_percentage_points": 20.0,
    }
    assert response["current"]["end_date_exclusive"] == response["previous"]["start_date"]\n    assert (date.fromisoformat(response["current"]["end_date_exclusive"]) - date.fromisoformat(response["current"]["start_date"])).days == 7\n    assert (date.fromisoformat(response["previous"]["end_date_exclusive"]) - date.fromisoformat(response["previous"]["start_date"])).days == 7
    assert "raw queries" in response["privacy"]
    assert "evidence IDs" in response["privacy"]

    assert session.execute.await_count == 2
    for call in session.execute.await_args_list:
        statement = call.args[0]
        assert "rag_feedback.organization_id" in str(statement)
        assert organization_id in statement.compile().params.values()


@pytest.mark.asyncio
async def test_feedback_comparison_handles_empty_previous_period_without_division(monkeypatch):
    user = SimpleNamespace(id=uuid4())
    membership = SimpleNamespace(organization_id=uuid4())
    session = AsyncMock()
    session.execute.side_effect = [
        _result([("helpful", 3)]),
        _result([]),
    ]

    async def membership_for_user(_user, _session):
        return membership

    monkeypatch.setattr(rag_operator, "get_membership", membership_for_user)
    response = await rag_operator.feedback_period_comparison(days=14, user=user, db=session)

    assert response["current"]["total"] == 3
    assert response["previous"]["total"] == 0
    assert response["change"]["total"] == {"absolute": 3, "percent": None}
    assert response["change"]["helpful"] == {"absolute": 3, "percent": None}
    assert response["change"]["helpful_rate_percentage_points"] is None

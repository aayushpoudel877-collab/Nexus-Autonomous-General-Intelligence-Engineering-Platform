from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services.api.app.core.dependencies import get_membership


class FakeScalarResult:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeSession:
    def __init__(self, values):
        self.values = values

    async def scalars(self, statement):
        return FakeScalarResult(self.values)


@pytest.mark.asyncio
async def test_membership_resolves_a_single_organization():
    membership = SimpleNamespace(organization_id=uuid4(), role_id=uuid4())
    resolved = await get_membership(
        SimpleNamespace(id=uuid4()), FakeSession([membership])
    )
    assert resolved is membership


@pytest.mark.asyncio
async def test_membership_rejects_accounts_without_organization():
    with pytest.raises(HTTPException) as error:
        await get_membership(SimpleNamespace(id=uuid4()), FakeSession([]))
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_selected_membership_resolves_exact_organization():
    user = SimpleNamespace(id=uuid4(), _selected_organization_id=None)
    selected_id = uuid4()
    memberships = [
        SimpleNamespace(organization_id=selected_id),
        SimpleNamespace(organization_id=uuid4()),
    ]
    user._selected_organization_id = selected_id
    resolved = await get_membership(user, FakeSession(memberships))
    assert resolved.organization_id == selected_id


@pytest.mark.asyncio
async def test_selected_membership_rejects_unavailable_organization():
    user = SimpleNamespace(id=uuid4(), _selected_organization_id=uuid4())
    with pytest.raises(HTTPException) as error:
        await get_membership(user, FakeSession([SimpleNamespace(organization_id=uuid4())]))
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_membership_fails_closed_for_multiple_organizations():
    user = SimpleNamespace(id=uuid4())
    memberships = [
        SimpleNamespace(organization_id=uuid4()),
        SimpleNamespace(organization_id=uuid4()),
    ]
    with pytest.raises(HTTPException) as error:
        await get_membership(user, FakeSession(memberships))
    assert error.value.status_code == 409
    assert "multiple organizations" in error.value.detail

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services.api.app.core.dependencies import get_developer_api_key
from services.api.app.db.base import Base
from services.api.app.services.ecosystem import (
    hash_api_key,
    normalize_scopes,
    generate_api_key,
)


def test_api_key_generation_is_verifiable_without_storing_plaintext():
    secret, prefix, digest = generate_api_key()

    assert secret.startswith("nxk_")
    assert prefix in secret
    assert digest == hash_api_key(secret)
    assert digest != secret


def test_api_key_scope_normalization_deduplicates():
    assert normalize_scopes(["plugin:write", "plugin:write", "plugin:read"]) == [
        "plugin:write",
        "plugin:read",
    ]


def test_api_key_scope_normalization_rejects_unknown_scope():
    with pytest.raises(ValueError):
        normalize_scopes(["root:everything"])


def test_phase_10_tables_are_registered_with_metadata():
    assert "developer_api_keys" in Base.metadata.tables
    assert "plugin_registrations" in Base.metadata.tables


def test_phase_10_routes_are_registered():
    from services.api.app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/developer/api-keys" in paths
    assert "/api/v1/developer/api-keys/{key_id}/revoke" in paths
    assert "/api/v1/developer/whoami" in paths
    assert "/api/v1/developer/plugins" in paths
    assert "/api/v1/developer/plugins/{plugin_id}" in paths


class FakeSession:
    def __init__(self, key):
        self.key = key
        self.committed = False

    async def scalar(self, statement):
        return self.key

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_developer_api_key_dependency_updates_last_used():
    key = SimpleNamespace(
        id=uuid4(),
        revoked_at=None,
        expires_at=None,
        last_used_at=None,
        scopes=["developer:read"],
    )
    session = FakeSession(key)

    result = await get_developer_api_key("nxk_test_secret", session)

    assert result is key
    assert key.last_used_at is not None
    assert session.committed


@pytest.mark.asyncio
async def test_developer_api_key_dependency_rejects_revoked_keys():
    key = SimpleNamespace(
        id=uuid4(),
        revoked_at="2026-10-01T00:00:00Z",
        expires_at=None,
        last_used_at=None,
        scopes=["developer:read"],
    )

    with pytest.raises(HTTPException) as error:
        await get_developer_api_key("nxk_test_secret", FakeSession(key))

    assert error.value.status_code == 401



def test_sdk_sends_the_developer_api_key(monkeypatch):
    from packages.sdk.client import NexusClient

    seen = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"status":"ok"}'

    def fake_urlopen(request, timeout):
        seen["headers"] = {key.lower(): value for key, value in request.header_items()}
        seen["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("packages.sdk.client.urlopen", fake_urlopen)
    result = NexusClient("http://localhost:8000/api/v1", "nxk_test_secret").whoami()

    assert result == {"status": "ok"}
    assert seen["headers"]["x-nexus-api-key"] == "nxk_test_secret"
    assert seen["timeout"] == 20.0


def test_sdk_converts_http_errors_to_nexus_api_errors(monkeypatch):
    from urllib.error import HTTPError
    from packages.sdk.client import NexusApiError, NexusClient

    def fake_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            403,
            "Forbidden",
            {},
            __import__("io").BytesIO(b'{"detail":"scope denied"}'),
        )

    monkeypatch.setattr("packages.sdk.client.urlopen", fake_urlopen)

    with pytest.raises(NexusApiError) as error:
        NexusClient("http://localhost:8000/api/v1", "nxk_test_secret").list_plugins()

    assert error.value.status_code == 403
    assert error.value.detail == {"detail": "scope denied"}

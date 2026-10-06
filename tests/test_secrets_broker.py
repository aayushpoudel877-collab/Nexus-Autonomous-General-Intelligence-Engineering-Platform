import asyncio
import base64
import json
import shlex
import sys
from pathlib import Path

import pytest

from services.secrets.broker import (
    MAX_SECRET_VALUE_BYTES,
    SecretBroker,
    SecretGrantSpec,
    SecretPolicyError,
    secret_ref_matches,
    secret_ref_sha256,
)
from services.secrets.process import _sanitized_environment, create_secret_broker


def test_secret_broker_environment_excludes_control_plane_secrets(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://secret")
    monkeypatch.setenv("NEXUS_SECRET_KEY", "super-secret")
    monkeypatch.setenv("REDIS_URL", "redis://secret")
    env = _sanitized_environment()
    assert "DATABASE_URL" not in env
    assert "NEXUS_SECRET_KEY" not in env
    assert "REDIS_URL" not in env


def test_secret_value_limit_is_bounded():
    assert MAX_SECRET_VALUE_BYTES == 64 * 1024


@pytest.mark.asyncio
async def test_secret_broker_rejects_unknown_grant(tmp_path, monkeypatch):
    async def fail_provider(_secret_ref):
        raise AssertionError("provider should not run")

    monkeypatch.setattr(
        "services.secrets.broker.resolve_secret",
        fail_provider,
    )
    broker = SecretBroker(
        grants=[
            SecretGrantSpec(
                grant_id="grant-1",
                secret_ref="secret://provider/key",
            )
        ],
        token="token-value",
        socket_path=str(tmp_path / "secret.sock"),
    )
    await broker.start()
    try:
        reader, writer = await asyncio.open_unix_connection(broker.socket_path)
        writer.write(
            (
                json.dumps({"token": "token-value", "grant_id": "unknown"})
                + "\n"
            ).encode()
        )
        await writer.drain()
        response = json.loads((await reader.readline()).decode())
        writer.close()
        await writer.wait_closed()
        assert response["ok"] is False
        assert "not approved" in response["error"]
    finally:
        await broker.stop()


@pytest.mark.asyncio
async def test_secret_broker_returns_only_requested_grant(tmp_path, monkeypatch):
    async def fake_provider(secret_ref):
        assert secret_ref == "secret://provider/key"
        return "fixture-secret"

    monkeypatch.setattr(
        "services.secrets.broker.resolve_secret",
        fake_provider,
    )
    broker = SecretBroker(
        grants=[
            SecretGrantSpec(
                grant_id="grant-1",
                secret_ref="secret://provider/key",
            )
        ],
        token="token-value",
        socket_path=str(tmp_path / "secret.sock"),
    )
    await broker.start()
    try:
        reader, writer = await asyncio.open_unix_connection(broker.socket_path)
        writer.write(
            (
                json.dumps({"token": "token-value", "grant_id": "grant-1"})
                + "\n"
            ).encode()
        )
        await writer.drain()
        response = json.loads((await reader.readline()).decode())
        writer.close()
        await writer.wait_closed()
        assert response["ok"] is True
        assert response["grant_id"] == "grant-1"
        assert base64.b64decode(response["secret_base64"]) == b"fixture-secret"
    finally:
        await broker.stop()


@pytest.mark.asyncio
async def test_secret_broker_subprocess_uses_external_provider_without_secrets_in_env(
    tmp_path, monkeypatch
):
    provider_script = (
        "import json,sys;"
        "request=json.load(sys.stdin);"
        "print(json.dumps({'ok':True,'secret':'fixture-secret'}))"
    )
    command = f"{shlex.quote(sys.executable)} -c {shlex.quote(provider_script)}"
    monkeypatch.setenv("NEXUS_SECRET_PROVIDER_COMMAND", command)

    broker, token_path = await create_secret_broker(
        runtime_root=str(tmp_path),
        execution_id="secret-test",
        grants=[
            SecretGrantSpec(
                grant_id="grant-1",
                secret_ref="secret://provider/key",
            )
        ],
    )
    try:
        token = Path(token_path).read_text(encoding="ascii")
        reader, writer = await asyncio.open_unix_connection(broker.socket_path)
        writer.write(
            (
                json.dumps({"token": token, "grant_id": "grant-1"})
                + "\n"
            ).encode()
        )
        await writer.drain()
        response = json.loads((await reader.readline()).decode())
        writer.close()
        await writer.wait_closed()
        assert response["ok"] is True
        assert base64.b64decode(response["secret_base64"]) == b"fixture-secret"
    finally:
        await broker.stop()


def test_secret_reference_fingerprint_is_stable_and_nonreversible_by_contract():
    reference = "secret://vault/nexus/github/token"
    fingerprint = secret_ref_sha256(reference)
    assert len(fingerprint) == 64
    assert secret_ref_matches(reference, fingerprint)
    assert not secret_ref_matches("secret://vault/nexus/github/other", fingerprint)
    assert secret_ref_matches(reference, fingerprint.upper())

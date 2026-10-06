"""Authenticated per-execution secret broker with no secret caching."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path
import shlex
import os
from typing import Any


MAX_PROTOCOL_LINE_BYTES = 64 * 1024
MAX_GRANTS = 8
MAX_SECRET_VALUE_BYTES = 64 * 1024
MAX_CONCURRENT_REQUESTS = 4


def secret_ref_sha256(secret_ref: str) -> str:
    return hashlib.sha256(secret_ref.encode("utf-8")).hexdigest()


def secret_ref_matches(secret_ref: str, fingerprint: str | None) -> bool:
    if fingerprint is None or len(fingerprint) != 64:
        return False
    return hmac.compare_digest(secret_ref_sha256(secret_ref), fingerprint)


class SecretPolicyError(ValueError):
    """Raised when a secret lookup violates the frozen execution policy."""


@dataclass(frozen=True)
class SecretGrantSpec:
    grant_id: str
    secret_ref: str


def _validate_grants(grants: list[SecretGrantSpec]) -> dict[str, str]:
    if not 1 <= len(grants) <= MAX_GRANTS:
        raise SecretPolicyError("Secret broker grants are outside the supported range")
    result: dict[str, str] = {}
    for grant in grants:
        if not grant.grant_id or len(grant.grant_id) > 64:
            raise SecretPolicyError("Secret grant ID is invalid")
        if not grant.secret_ref.startswith("secret://"):
            raise SecretPolicyError("Secret grant reference is invalid")
        if any(ch in grant.secret_ref for ch in ("\x00", "\r", "\n")):
            raise SecretPolicyError("Secret grant reference contains control characters")
        result[grant.grant_id] = grant.secret_ref
    return result


def _provider_command() -> list[str]:
    raw = os.getenv("NEXUS_SECRET_PROVIDER_COMMAND", "").strip()
    if not raw:
        raise SecretPolicyError("No external secret provider is configured")
    try:
        command = shlex.split(raw)
    except ValueError as exc:
        raise SecretPolicyError("Secret provider command is invalid") from exc
    if not command:
        raise SecretPolicyError("Secret provider command is empty")
    if any(any(ch in part for ch in ("\x00", "\r", "\n")) for part in command):
        raise SecretPolicyError("Secret provider command contains control characters")
    return command


async def resolve_secret(secret_ref: str) -> str:
    command = _provider_command()
    provider = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env={
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "PYTHONPATH", "PYTHONUNBUFFERED", "SSL_CERT_FILE", "SSL_CERT_DIR"}
        },
    )
    request = json.dumps({"secret_ref": secret_ref}, separators=(",", ":")).encode("utf-8")
    try:
        stdout, _stderr = await asyncio.wait_for(
            provider.communicate(input=request),
            timeout=5,
        )
    except asyncio.TimeoutError:
        try:
            provider.kill()
        except ProcessLookupError:
            pass
        await provider.wait()
        raise SecretPolicyError("External secret provider timed out")
    if provider.returncode != 0:
        raise SecretPolicyError("External secret provider failed")
    if len(stdout) > MAX_SECRET_VALUE_BYTES * 2:
        raise SecretPolicyError("External secret provider response is too large")
    try:
        payload = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SecretPolicyError("External secret provider returned invalid JSON") from exc
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise SecretPolicyError("External secret provider did not return a secret")
    value = payload.get("secret")
    if not isinstance(value, str) or not value:
        raise SecretPolicyError("External secret provider returned an invalid secret")
    if len(value.encode("utf-8")) > MAX_SECRET_VALUE_BYTES:
        raise SecretPolicyError("Secret value exceeds the broker limit")
    return value


class SecretBroker:
    """Per-execution broker exposing only explicitly granted opaque IDs."""

    def __init__(self, *, grants: list[SecretGrantSpec], token: str, socket_path: str) -> None:
        if not token or any(ch in token for ch in ("\x00", "\r", "\n")):
            raise ValueError("Secret broker token is invalid")
        self.grants = _validate_grants(grants)
        self.token = token
        self.socket_path = str(Path(socket_path))
        self._server: asyncio.AbstractServer | None = None
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self._tasks: set[asyncio.Task[None]] = set()

    async def start(self) -> None:
        path = Path(self.socket_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=self.socket_path,
            limit=MAX_PROTOCOL_LINE_BYTES,
        )
        path.chmod(0o666)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        Path(self.socket_path).unlink(missing_ok=True)

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        task = asyncio.current_task()
        if task is not None:
            self._tasks.add(task)
        try:
            async with self._semaphore:
                await self._serve_request(reader, writer)
        finally:
            if task is not None:
                self._tasks.discard(task)
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    async def _serve_request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        response: dict[str, Any]
        try:
            raw = await reader.readuntil(b"\n")
            if len(raw) > MAX_PROTOCOL_LINE_BYTES:
                raise SecretPolicyError("Secret broker request is too large")
            request = json.loads(raw.decode("utf-8"))
            if not isinstance(request, dict):
                raise SecretPolicyError("Secret broker request must be an object")
            token = request.get("token")
            if not isinstance(token, str) or not hmac.compare_digest(token, self.token):
                raise SecretPolicyError("Secret broker authentication failed")
            grant_id = request.get("grant_id")
            if not isinstance(grant_id, str) or grant_id not in self.grants:
                raise SecretPolicyError("Secret grant is not approved for this execution")
            secret = await resolve_secret(self.grants[grant_id])
            response = {
                "ok": True,
                "grant_id": grant_id,
                "secret_base64": base64.b64encode(secret.encode("utf-8")).decode("ascii"),
            }
        except (
            SecretPolicyError,
            json.JSONDecodeError,
            UnicodeDecodeError,
            asyncio.LimitOverrunError,
            asyncio.IncompleteReadError,
            binascii.Error,
            OSError,
            ValueError,
            TypeError,
            asyncio.TimeoutError,
        ) as exc:
            response = {"ok": False, "error": str(exc)[:500]}
        except asyncio.CancelledError:
            raise
        writer.write((json.dumps(response, separators=(",", ":")) + "\n").encode("utf-8"))
        await writer.drain()

"""Isolated subprocess lifecycle for per-execution secret mediation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
import signal
import sys
import uuid

from .broker import SecretGrantSpec, SecretBroker

BROKER_START_TIMEOUT_SECONDS = 5
BROKER_STOP_TIMEOUT_SECONDS = 5


def _sanitized_environment() -> dict[str, str]:
    keep = {
        "PATH",
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "NEXUS_SECRET_PROVIDER_COMMAND",
    }
    return {key: value for key, value in os.environ.items() if key in keep and value}


@dataclass
class SecretBrokerProcess:
    process: asyncio.subprocess.Process
    socket_path: str
    token_path: str
    config_path: str

    async def stop(self) -> None:
        if self.process.returncode is None:
            try:
                self.process.send_signal(signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(
                    self.process.wait(),
                    timeout=BROKER_STOP_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                try:
                    self.process.kill()
                except ProcessLookupError:
                    pass
                await self.process.wait()
        for path in (self.socket_path, self.token_path, self.config_path):
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass


async def create_secret_broker(
    *,
    runtime_root: str,
    execution_id: str,
    grants: list[SecretGrantSpec],
) -> tuple[SecretBrokerProcess, str]:
    root = Path(runtime_root).resolve() / "secrets"
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    token = uuid.uuid4().hex + uuid.uuid4().hex
    socket_path = root / f"{execution_id}.sock"
    token_path = root / f"{execution_id}.token"
    config_path = root / f"{execution_id}.json"
    token_path.write_text(token, encoding="ascii")
    token_path.chmod(0o644)
    config_path.write_text(
        json.dumps(
            {
                "grants": [
                    {"grant_id": grant.grant_id, "secret_ref": grant.secret_ref}
                    for grant in grants
                ]
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    config_path.chmod(0o600)

    process: asyncio.subprocess.Process | None = None
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "services.secrets.server",
            "--socket",
            str(socket_path),
            "--token-file",
            str(token_path),
            "--config",
            str(config_path),
            env=_sanitized_environment(),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
        deadline = asyncio.get_running_loop().time() + BROKER_START_TIMEOUT_SECONDS
        while not socket_path.exists():
            if process.returncode is not None:
                raise OSError("Secret broker exited during startup")
            if asyncio.get_running_loop().time() >= deadline:
                raise OSError("Secret broker did not create its socket in time")
            await asyncio.sleep(0.05)
        return (
            SecretBrokerProcess(
                process=process,
                socket_path=str(socket_path),
                token_path=str(token_path),
                config_path=str(config_path),
            ),
            str(token_path),
        )
    except (OSError, ValueError):
        if process is not None and process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
        for path in (socket_path, token_path, config_path):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        raise

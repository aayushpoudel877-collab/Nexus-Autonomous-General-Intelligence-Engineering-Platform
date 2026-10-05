"""Isolated subprocess lifecycle for the per-execution egress broker."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
import signal
import sys
import uuid


BROKER_START_TIMEOUT_SECONDS = 5.0
BROKER_STOP_TIMEOUT_SECONDS = 5.0


def _sanitized_environment() -> dict[str, str]:
    keep = {"PATH", "PYTHONPATH", "PYTHONUNBUFFERED", "SSL_CERT_FILE", "SSL_CERT_DIR"}
    return {
        key: value
        for key, value in os.environ.items()
        if key in keep and value
    }


@dataclass
class EgressBrokerProcess:
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


async def create_egress_broker(
    *,
    runtime_root: str,
    execution_id: str | None,
    allowlist: list[str],
    request_timeout_seconds: float,
    max_request_bytes: int,
    max_response_bytes: int,
) -> tuple[EgressBrokerProcess, str]:
    execution_token = execution_id or uuid.uuid4().hex
    root = Path(runtime_root).resolve() / "egress"
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)

    token = uuid.uuid4().hex + uuid.uuid4().hex
    socket_path = root / f"{execution_token}.sock"
    token_path = root / f"{execution_token}.token"
    config_path = root / f"{execution_token}.json"

    token_path.write_text(token, encoding="ascii")
    token_path.chmod(0o644)
    config_path.write_text(
        json.dumps(
            {
                "allowlist": allowlist,
                "request_timeout_seconds": request_timeout_seconds,
                "max_request_bytes": max_request_bytes,
                "max_response_bytes": max_response_bytes,
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
            "services.egress.server",
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
                raise OSError("Egress broker exited during startup")
            if asyncio.get_running_loop().time() >= deadline:
                raise OSError("Egress broker did not create its socket in time")
            await asyncio.sleep(0.05)
        return (
            EgressBrokerProcess(
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

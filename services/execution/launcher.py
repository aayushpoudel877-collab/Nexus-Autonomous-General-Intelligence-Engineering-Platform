"""Bounded subprocess launcher for the isolated OCI runtime."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
import signal
import uuid


class LauncherOutputLimitExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class LauncherResult:
    exit_code: int | None
    timed_out: bool
    output_limited: bool
    stdout: bytes
    stderr: bytes
    duration_seconds: float


async def _read_limited(
    stream: asyncio.StreamReader | None,
    *,
    limit: int,
    shared: dict[str, int],
) -> bytes:
    if stream is None:
        return b""
    chunks: list[bytes] = []
    local = 0
    while True:
        chunk = await stream.read(min(64 * 1024, limit - local + 1))
        if not chunk:
            break
        remaining = limit - local
        if len(chunk) > remaining:
            if remaining:
                chunks.append(chunk[:remaining])
                local += remaining
                shared["used"] += remaining
            raise LauncherOutputLimitExceeded("Sandbox output exceeded the execution limit")
        chunks.append(chunk)
        local += len(chunk)
        shared["used"] += len(chunk)
        if shared["used"] > limit:
            raise LauncherOutputLimitExceeded("Sandbox output exceeded the execution limit")
    return b"".join(chunks)


async def _terminate_process(process: asyncio.subprocess.Process, grace_seconds: int) -> None:
    if process.returncode is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (OSError, PermissionError):
        try:
            process.terminate()
        except OSError:
            return
    try:
        await asyncio.wait_for(process.wait(), timeout=grace_seconds)
        return
    except asyncio.TimeoutError:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (OSError, PermissionError):
        try:
            process.kill()
        except OSError:
            return
    await process.wait()


async def _cleanup_container(
    *,
    docker_binary: str,
    cidfile: Path,
    timeout_seconds: float = 5.0,
) -> None:
    try:
        container_id = cidfile.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return
    if not container_id:
        return
    try:
        cleanup = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                docker_binary,
                "rm",
                "-f",
                container_id,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            ),
            timeout=timeout_seconds,
        )
        await asyncio.wait_for(cleanup.wait(), timeout=timeout_seconds)
    except (OSError, asyncio.TimeoutError):
        return


async def launch_sandbox(
    *,
    command: list[str],
    cidfile: str,
    timeout_seconds: int,
    max_output_bytes: int,
    stop_grace_seconds: int,
) -> LauncherResult:
    if not command:
        raise ValueError("Sandbox command cannot be empty")
    if timeout_seconds < 1 or timeout_seconds > 3600:
        raise ValueError("Sandbox timeout must be between 1 and 3600 seconds")
    if max_output_bytes < 4096 or max_output_bytes > 16 * 1024 * 1024:
        raise ValueError("Sandbox output limit is outside the supported range")
    if stop_grace_seconds < 1 or stop_grace_seconds > 30:
        raise ValueError("Sandbox stop grace period is outside the supported range")

    cid_path = Path(cidfile)
    cid_path.parent.mkdir(parents=True, exist_ok=True)
    if cid_path.exists():
        cid_path.unlink()

    started = asyncio.get_running_loop().time()
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    shared = {"used": 0}
    per_stream_limit = max(1024, max_output_bytes // 2)
    stdout_task = asyncio.create_task(
        _read_limited(process.stdout, limit=per_stream_limit, shared=shared)
    )
    stderr_task = asyncio.create_task(
        _read_limited(process.stderr, limit=per_stream_limit, shared=shared)
    )

    timed_out = False
    output_limited = False
    try:
        stdout, stderr = await asyncio.wait_for(
            asyncio.gather(stdout_task, stderr_task),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        timed_out = True
        stdout_task.cancel()
        stderr_task.cancel()
        await _terminate_process(process, stop_grace_seconds)
        await _cleanup_container(docker_binary=command[0], cidfile=cid_path)
        stdout = b""
        stderr = b""
    except LauncherOutputLimitExceeded:
        output_limited = True
        stdout_task.cancel()
        stderr_task.cancel()
        await _terminate_process(process, stop_grace_seconds)
        await _cleanup_container(docker_binary=command[0], cidfile=cid_path)
        stdout = b""
        stderr = b""
    else:
        await process.wait()
        cid_path.unlink(missing_ok=True)

    stdout_task.cancel()
    stderr_task.cancel()
    for task in (stdout_task, stderr_task):
        try:
            await task
        except (asyncio.CancelledError, LauncherOutputLimitExceeded):
            pass

    duration = asyncio.get_running_loop().time() - started
    return LauncherResult(
        exit_code=process.returncode,
        timed_out=timed_out,
        output_limited=output_limited,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=duration,
    )


def new_cidfile(root: str) -> str:
    path = Path(root).resolve() / "cid" / f"{uuid.uuid4().hex}.cid"
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)

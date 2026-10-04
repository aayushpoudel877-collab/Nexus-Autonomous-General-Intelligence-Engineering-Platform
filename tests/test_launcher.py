import asyncio

import pytest

from services.execution.launcher import LauncherOutputLimitExceeded, launch_sandbox, new_cidfile


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def read(self, _limit):
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


class _FakeProcess:
    def __init__(self, stdout=b"ok", stderr=b"", returncode=0):
        self.stdout = _FakeStream([stdout, b""])
        self.stderr = _FakeStream([stderr, b""])
        self.returncode = None
        self._final_returncode = returncode
        self.pid = 43210

    async def wait(self):
        self.returncode = self._final_returncode
        return self.returncode

    def terminate(self):
        self.returncode = -15

    def kill(self):
        self.returncode = -9


@pytest.mark.asyncio
async def test_launcher_uses_exec_without_shell(tmp_path, monkeypatch):
    calls = []

    async def fake_create(*args, **kwargs):
        calls.append((args, kwargs))
        return _FakeProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    cidfile = new_cidfile(str(tmp_path))

    result = await launch_sandbox(
        command=["docker", "run", "--network=none", "image@sha256:" + "a" * 64],
        cidfile=cidfile,
        timeout_seconds=10,
        max_output_bytes=4096,
        stop_grace_seconds=2,
    )

    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.output_limited is False
    assert calls
    assert calls[0][0][0] == "docker"
    assert calls[0][1]["start_new_session"] is True
    assert calls[0][1]["stdin"] is asyncio.subprocess.DEVNULL


@pytest.mark.asyncio
async def test_launcher_rejects_invalid_limits(tmp_path):
    with pytest.raises(ValueError):
        await launch_sandbox(
            command=["docker", "run"],
            cidfile=str(tmp_path / "cid"),
            timeout_seconds=0,
            max_output_bytes=4096,
            stop_grace_seconds=2,
        )


@pytest.mark.asyncio
async def test_launcher_output_limit_exception_type_is_public():
    assert issubclass(LauncherOutputLimitExceeded, RuntimeError)

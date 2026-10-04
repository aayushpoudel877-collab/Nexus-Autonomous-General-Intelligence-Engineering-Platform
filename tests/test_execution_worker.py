import hashlib

import pytest

from services.api.app.models import ExecutionRequest
from services.execution.executor import SandboxAdmissionExecutor


@pytest.mark.asyncio
async def test_phase_15_worker_fails_closed_before_external_plugin_execution():
    request = ExecutionRequest(
        entrypoint="plugin.run",
        input_json={"hello": "world"},
        max_output_bytes=4096,
    )

    outcome = await SandboxAdmissionExecutor().execute(request)

    assert outcome.success is False
    assert outcome.error_code == "artifact_admission_rejected"
    assert outcome.result["status"] == "blocked"
    assert outcome.output_bytes <= request.max_output_bytes


def test_phase_15_worker_package_is_importable():
    from services.execution.config import settings

    assert settings.worker_id
    assert settings.poll_seconds > 0
    assert settings.lease_seconds >= 5



@pytest.mark.asyncio
async def test_phase_15_worker_requires_staged_verified_artifact(tmp_path, monkeypatch):
    from services.execution.config import settings

    monkeypatch.setattr(settings, "artifact_root", str(tmp_path))
    request = ExecutionRequest(
        entrypoint="plugin.run",
        input_json={"hello": "world"},
        max_output_bytes=4096,
        policy_snapshot={
            "version": 2,
            "execution": {
                "sandbox_required": True,
                "artifact_verification_required": True,
                "artifact_verified": True,
            },
            "provenance": {
                "package_sha256": "a" * 64,
                "artifact_storage_key": "a" * 64,
                "artifact_size_bytes": "12",
            },
            "limits": {"max_memory_mb": 256},
            "network": {"policy": "none", "allowlist": []},
        },
    )

    outcome = await SandboxAdmissionExecutor().execute(request)

    assert outcome.success is False
    assert outcome.error_code == "artifact_admission_rejected"



@pytest.mark.asyncio
async def test_phase_15_worker_prepares_pinned_sandbox_after_verified_artifact(
    tmp_path, monkeypatch
):
    from services.api.app.services.artifact_store import ArtifactStore
    from services.execution.config import settings

    artifact = b"verified-runtime-artifact"
    digest = hashlib.sha256(artifact).hexdigest()
    store = ArtifactStore(str(tmp_path), max_bytes=6 * 1024 * 1024)
    store.put_verified(artifact, digest)

    monkeypatch.setattr(settings, "artifact_root", str(tmp_path))
    monkeypatch.setattr(
        settings,
        "sandbox_image",
        "registry.example/nexus-runtime@sha256:" + "a" * 64,
    )

    request = ExecutionRequest(
        entrypoint="plugin.run",
        input_json={},
        max_output_bytes=4096,
        max_memory_mb=256,
        policy_snapshot={
            "version": 2,
            "execution": {
                "sandbox_required": True,
                "artifact_verification_required": True,
                "artifact_verified": True,
            },
            "provenance": {
                "package_sha256": digest,
                "artifact_storage_key": digest,
                "artifact_size_bytes": str(len(artifact)),
            },
            "limits": {"max_memory_mb": 256},
            "network": {"policy": "none", "allowlist": []},
        },
    )

    outcome = await SandboxAdmissionExecutor().execute(request)

    assert outcome.success is False
    assert outcome.error_code == "sandbox_launcher_disabled"
    assert outcome.result["status"] == "sandbox_prepared"
    assert outcome.result["artifact_digest"] == digest



@pytest.mark.asyncio
async def test_phase_16_worker_launches_only_when_explicitly_enabled(
    tmp_path, monkeypatch
):
    from services.api.app.services.artifact_store import ArtifactStore
    from services.execution.config import settings

    artifact = b"verified-runtime-artifact"
    digest = hashlib.sha256(artifact).hexdigest()
    ArtifactStore(str(tmp_path), max_bytes=6 * 1024 * 1024).put_verified(artifact, digest)

    monkeypatch.setattr(settings, "artifact_root", str(tmp_path))
    monkeypatch.setattr(settings, "runtime_root", str(tmp_path / "runtime"))
    monkeypatch.setattr(
        settings,
        "sandbox_image",
        "registry.example/nexus-runtime@sha256:" + "a" * 64,
    )
    monkeypatch.setattr(settings, "sandbox_launch_enabled", False)

    request = ExecutionRequest(
        entrypoint="plugin.run",
        input_json={},
        max_output_bytes=4096,
        max_memory_mb=256,
        policy_snapshot={
            "version": 2,
            "execution": {
                "sandbox_required": True,
                "artifact_verification_required": True,
                "artifact_verified": True,
            },
            "provenance": {
                "package_sha256": digest,
                "artifact_storage_key": digest,
                "artifact_size_bytes": str(len(artifact)),
            },
            "limits": {"max_memory_mb": 256},
            "network": {"policy": "none", "allowlist": []},
        },
    )

    outcome = await SandboxAdmissionExecutor().execute(request)

    assert outcome.success is False
    assert outcome.error_code == "sandbox_launcher_disabled"


@pytest.mark.asyncio
async def test_phase_16_worker_classifies_missing_sandbox_runtime(
    tmp_path, monkeypatch
):
    import services.execution.executor as executor_module
    from services.api.app.services.artifact_store import ArtifactStore
    from services.execution.config import settings

    artifact = b"test"
    import hashlib

    digest = hashlib.sha256(artifact).hexdigest()
    ArtifactStore(str(tmp_path), max_bytes=6 * 1024 * 1024).put_verified(
        artifact,
        digest,
    )
    monkeypatch.setattr(settings, "artifact_root", str(tmp_path))
    monkeypatch.setattr(settings, "runtime_root", str(tmp_path / "runtime"))
    monkeypatch.setattr(settings, "sandbox_launch_enabled", True)
    monkeypatch.setattr(
        settings,
        "sandbox_image",
        "registry.example/nexus-runtime@sha256:" + "a" * 64,
    )

    async def unavailable_runtime(**_kwargs):
        raise OSError("docker unavailable")

    monkeypatch.setattr(executor_module, "launch_sandbox", unavailable_runtime)

    request = ExecutionRequest(
        entrypoint="plugin.run",
        input_json={},
        max_output_bytes=4096,
        max_memory_mb=256,
        policy_snapshot={
            "version": 2,
            "execution": {
                "sandbox_required": True,
                "artifact_verification_required": True,
                "artifact_verified": True,
            },
            "provenance": {
                "package_sha256": digest,
                "artifact_storage_key": digest,
                "artifact_size_bytes": str(len(artifact)),
            },
            "limits": {"max_memory_mb": 256},
            "network": {"policy": "none", "allowlist": []},
        },
    )

    outcome = await SandboxAdmissionExecutor().execute(request)

    assert outcome.success is False
    assert outcome.error_code == "sandbox_runtime_unavailable"


@pytest.mark.asyncio
async def test_phase_16_worker_records_successful_sandbox_result(
    tmp_path, monkeypatch
):
    import services.execution.executor as executor_module
    from services.api.app.services.artifact_store import ArtifactStore
    from services.execution.config import settings
    from services.execution.launcher import LauncherResult

    artifact = b"verified"
    import hashlib

    digest = hashlib.sha256(artifact).hexdigest()
    ArtifactStore(str(tmp_path), max_bytes=6 * 1024 * 1024).put_verified(
        artifact,
        digest,
    )
    monkeypatch.setattr(settings, "artifact_root", str(tmp_path))
    monkeypatch.setattr(settings, "runtime_root", str(tmp_path / "runtime"))
    monkeypatch.setattr(settings, "sandbox_launch_enabled", True)
    monkeypatch.setattr(
        settings,
        "sandbox_image",
        "registry.example/nexus-runtime@sha256:" + "a" * 64,
    )

    async def successful_runtime(**_kwargs):
        return LauncherResult(
            exit_code=0,
            timed_out=False,
            output_limited=False,
            stdout=b"ok",
            stderr=b"",
            duration_seconds=0.25,
        )

    monkeypatch.setattr(executor_module, "launch_sandbox", successful_runtime)

    request = ExecutionRequest(
        entrypoint="plugin.run",
        input_json={},
        max_output_bytes=4096,
        max_memory_mb=256,
        timeout_seconds=30,
        policy_snapshot={
            "version": 2,
            "execution": {
                "sandbox_required": True,
                "artifact_verification_required": True,
                "artifact_verified": True,
            },
            "provenance": {
                "package_sha256": digest,
                "artifact_storage_key": digest,
                "artifact_size_bytes": str(len(artifact)),
            },
            "limits": {"max_memory_mb": 256},
            "network": {"policy": "none", "allowlist": []},
        },
    )

    outcome = await SandboxAdmissionExecutor().execute(request)

    assert outcome.success is True
    assert outcome.error_code is None
    assert outcome.result["status"] == "succeeded"
    assert outcome.result["stdout"] == "ok"

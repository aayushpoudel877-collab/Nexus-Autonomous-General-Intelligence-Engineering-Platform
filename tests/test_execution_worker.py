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
    assert outcome.error_code == "sandbox_launcher_not_enabled"
    assert outcome.result["status"] == "sandbox_prepared"
    assert outcome.result["artifact_digest"] == digest

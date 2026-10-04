from dataclasses import dataclass
from typing import Any

from services.api.app.models import ExecutionRequest
from services.api.app.services.artifact_store import ArtifactStore
from services.api.app.services.execution import normalize_execution_result

from .admission import admit_verified_artifact
from .config import settings
from .sandbox import build_oci_command


@dataclass(frozen=True)
class ExecutionOutcome:
    success: bool
    result: dict[str, Any]
    output_bytes: int
    error_code: str | None = None
    failure_reason: str | None = None


class ExecutionBackend:
    """Execution boundary for the isolated runtime."""

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        raise NotImplementedError


class SandboxAdmissionExecutor(ExecutionBackend):
    """Admit only verified artifacts and compile a sandbox command; never run it here."""

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        try:
            admission = admit_verified_artifact(
                policy_snapshot=request.policy_snapshot,
                artifact_store=ArtifactStore(
                    settings.artifact_root,
                    max_bytes=6 * 1024 * 1024,
                ),
            )
        except (OSError, ValueError) as exc:
            result = {
                "status": "blocked",
                "entrypoint": request.entrypoint,
            }
            normalized, size = normalize_execution_result(
                result,
                max_output_bytes=request.max_output_bytes,
            )
            return ExecutionOutcome(
                success=False,
                result=normalized,
                output_bytes=size,
                error_code="artifact_admission_rejected",
                failure_reason=str(exc)[:1000],
            )

        if not settings.sandbox_image:
            result = {
                "status": "blocked",
                "entrypoint": request.entrypoint,
                "artifact_digest": admission.artifact_digest,
            }
            normalized, size = normalize_execution_result(
                result,
                max_output_bytes=request.max_output_bytes,
            )
            return ExecutionOutcome(
                success=False,
                result=normalized,
                output_bytes=size,
                error_code="sandbox_not_configured",
                failure_reason=(
                    "No digest-pinned OCI sandbox image is configured; "
                    "verified plugin execution remains fail-closed."
                ),
            )

        try:
            command = build_oci_command(
                image=settings.sandbox_image,
                artifact_path=(
                    f"{settings.artifact_root}/"
                    f"{admission.artifact_digest[:2]}/"
                    f"{admission.artifact_digest[2:4]}/"
                    f"{admission.artifact_digest}"
                ),
                entrypoint=request.entrypoint,
                max_memory_mb=request.max_memory_mb,
            )
        except ValueError as exc:
            result = {
                "status": "blocked",
                "entrypoint": request.entrypoint,
                "artifact_digest": admission.artifact_digest,
            }
            normalized, size = normalize_execution_result(
                result,
                max_output_bytes=request.max_output_bytes,
            )
            return ExecutionOutcome(
                success=False,
                result=normalized,
                output_bytes=size,
                error_code="sandbox_policy_rejected",
                failure_reason=str(exc)[:1000],
            )

        result = {
            "status": "sandbox_prepared",
            "entrypoint": request.entrypoint,
            "artifact_digest": admission.artifact_digest,
            "sandbox_image": command.image,
            "network_policy": admission.network_policy,
        }
        normalized, size = normalize_execution_result(
            result,
            max_output_bytes=request.max_output_bytes,
        )
        return ExecutionOutcome(
            success=False,
            result=normalized,
            output_bytes=size,
            error_code="sandbox_launcher_not_enabled",
            failure_reason=(
                "The verified artifact passed sandbox admission, but Phase 15 does not "
                "launch external plugin code yet."
            ),
        )

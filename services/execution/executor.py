from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from services.api.app.models import ExecutionRequest
from services.secrets.broker import SecretGrantSpec
from services.api.app.services.artifact_store import ArtifactStore
from services.api.app.services.execution import normalize_execution_result

from .admission import admit_verified_artifact
from .config import settings
from .launcher import launch_sandbox, new_cidfile
from services.egress.process import create_egress_broker
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

    async def execute(
        self,
        request: ExecutionRequest,
        cancellation_check: Callable[[], Awaitable[bool]] | None = None,
        secret_grants: list[SecretGrantSpec] | None = None,
    ) -> ExecutionOutcome:
        raise NotImplementedError


def _bounded_launch_result(
    *,
    status: str,
    request: ExecutionRequest,
    artifact_digest: str,
    sandbox_image: str,
    exit_code: int | None,
    duration_seconds: float,
    timed_out: bool,
    output_limited: bool,
    stdout: bytes,
    stderr: bytes,
) -> tuple[dict[str, Any], int]:
    result = {
        "status": status,
        "entrypoint": request.entrypoint,
        "artifact_digest": artifact_digest,
        "sandbox_image": sandbox_image,
        "exit_code": exit_code,
        "duration_seconds": round(duration_seconds, 3),
        "timed_out": timed_out,
        "output_limited": output_limited,
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
    }
    try:
        return normalize_execution_result(
            result,
            max_output_bytes=request.max_output_bytes,
        )
    except ValueError:
        compact = dict(result)
        compact["stdout"] = compact["stdout"][:256]
        compact["stderr"] = compact["stderr"][:256]
        return normalize_execution_result(
            compact,
            max_output_bytes=request.max_output_bytes,
        )


class SandboxAdmissionExecutor(ExecutionBackend):
    """Verify, admit and optionally launch plugin code inside the isolated sandbox."""

    async def execute(
        self,
        request: ExecutionRequest,
        cancellation_check: Callable[[], Awaitable[bool]] | None = None,
        secret_grants: list[SecretGrantSpec] | None = None,
    ) -> ExecutionOutcome:
        try:
            admission = admit_verified_artifact(
                policy_snapshot=request.policy_snapshot,
                artifact_store=ArtifactStore(
                    settings.artifact_root,
                    max_bytes=6 * 1024 * 1024,
                ),
            )
        except (OSError, TypeError, ValueError):
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
                failure_reason=(
                    "The verified artifact could not pass sandbox admission; "
                    "the worker did not execute plugin code."
                ),
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

        if not settings.sandbox_launch_enabled:
            result = {
                "status": "sandbox_prepared",
                "entrypoint": request.entrypoint,
                "artifact_digest": admission.artifact_digest,
                "sandbox_image": settings.sandbox_image,
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
                error_code="sandbox_launcher_disabled",
                failure_reason=(
                    "The isolated launcher is disabled; Phase 16 requires explicit "
                    "runtime opt-in before plugin code can execute."
                ),
            )

        egress_broker = None
        egress_token_path = None
        secret_broker = None
        secret_token_path = None
        cidfile = new_cidfile(settings.runtime_root)
        try:
            if admission.secret_required:
                if not secret_grants or len(secret_grants) != len(admission.secret_grant_ids):
                    result = {"status": "blocked", "entrypoint": request.entrypoint}
                    normalized, size = normalize_execution_result(
                        result, max_output_bytes=request.max_output_bytes
                    )
                    return ExecutionOutcome(
                        success=False,
                        result=normalized,
                        output_bytes=size,
                        error_code="secret_broker_unavailable",
                        failure_reason="Approved secret grants are not available to the worker.",
                    )
                expected_grants = set(admission.secret_grant_ids)
                provided_grants = {grant.grant_id for grant in secret_grants}
                if provided_grants != expected_grants:
                    result = {"status": "blocked", "entrypoint": request.entrypoint}
                    normalized, size = normalize_execution_result(
                        result, max_output_bytes=request.max_output_bytes
                    )
                    return ExecutionOutcome(
                        success=False,
                        result=normalized,
                        output_bytes=size,
                        error_code="secret_broker_unavailable",
                        failure_reason="The worker secret grant set does not match the frozen execution policy.",
                    )
                from services.secrets.process import create_secret_broker
                try:
                    secret_broker, secret_token_path = await create_secret_broker(
                        runtime_root=settings.runtime_root,
                        execution_id=str(request.id),
                        grants=secret_grants,
                    )
                except (OSError, TypeError, ValueError) as exc:
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
                        error_code="secret_broker_unavailable",
                        failure_reason=str(exc)[:500],
                    )

            if admission.egress_required:
                try:
                    egress_broker, egress_token_path = await create_egress_broker(
                        runtime_root=settings.runtime_root,
                        execution_id=str(request.id),
                        allowlist=admission.network_allowlist,
                        request_timeout_seconds=min(
                            request.timeout_seconds,
                            request.policy_snapshot["egress"]["timeout_seconds"],
                        ),
                        max_request_bytes=request.policy_snapshot["egress"]["max_request_bytes"],
                        max_response_bytes=request.policy_snapshot["egress"]["max_response_bytes"],
                    )
                except (OSError, TypeError, ValueError) as exc:
                    result = {
                        "status": "blocked",
                        "entrypoint": request.entrypoint,
                        "artifact_digest": admission.artifact_digest,
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
                        error_code="egress_broker_unavailable",
                        failure_reason=str(exc)[:500],
                    )

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
                cidfile=cidfile,
                docker_binary=settings.docker_binary,
                egress_socket_path=egress_broker.socket_path if egress_broker else None,
                egress_token_path=egress_token_path,
                secret_socket_path=secret_broker.socket_path if secret_broker else None,
                secret_token_path=secret_token_path,
            )

            try:
                launch = await launch_sandbox(
                    command=command.command,
                    cidfile=command.cidfile,
                    timeout_seconds=request.timeout_seconds,
                    max_output_bytes=request.max_output_bytes,
                    stop_grace_seconds=settings.sandbox_stop_grace_seconds,
                    cancellation_check=cancellation_check,
                    cancellation_poll_seconds=settings.sandbox_cancellation_poll_seconds,
                )
            except (OSError, ValueError):
                result, size = _bounded_launch_result(
                    status="runtime_unavailable",
                    request=request,
                    artifact_digest=admission.artifact_digest,
                    sandbox_image=command.image,
                    exit_code=None,
                    duration_seconds=0.0,
                    timed_out=False,
                    output_limited=False,
                    stdout=b"",
                    stderr=b"",
                )
                return ExecutionOutcome(
                    success=False,
                    result=result,
                    output_bytes=size,
                    error_code="sandbox_runtime_unavailable",
                    failure_reason="The isolated sandbox runtime could not be started.",
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
        finally:
            if egress_broker is not None:
                await egress_broker.stop()
            if egress_token_path:
                try:
                    from pathlib import Path
                    Path(egress_token_path).unlink(missing_ok=True)
                except OSError:
                    pass
            if secret_broker is not None:
                await secret_broker.stop()
            if secret_token_path:
                try:
                    from pathlib import Path
                    Path(secret_token_path).unlink(missing_ok=True)
                except OSError:
                    pass

        if launch.cancelled:
            status = "cancelled"
            success = False
            error_code = "sandbox_cancelled"
            reason = "Sandbox execution was cancelled by the request owner."
        elif launch.timed_out:
            status = "timeout"
            success = False
            error_code = "sandbox_timeout"
            reason = "Sandbox execution exceeded the request timeout."
        elif launch.output_limited:
            status = "output_limit"
            success = False
            error_code = "sandbox_output_limit"
            reason = "Sandbox output exceeded the request output limit."
        elif launch.exit_code == 0:
            status = "succeeded"
            success = True
            error_code = None
            reason = None
        else:
            status = "failed"
            success = False
            error_code = "sandbox_exit"
            reason = "Sandbox process exited with a non-zero status."

        result, size = _bounded_launch_result(
            status=status,
            request=request,
            artifact_digest=admission.artifact_digest,
            sandbox_image=command.image,
            exit_code=launch.exit_code,
            duration_seconds=launch.duration_seconds,
            timed_out=launch.timed_out,
            output_limited=launch.output_limited,
            stdout=launch.stdout,
            stderr=launch.stderr,
        )
        return ExecutionOutcome(
            success=success,
            result=result,
            output_bytes=size,
            error_code=error_code,
            failure_reason=reason,
        )

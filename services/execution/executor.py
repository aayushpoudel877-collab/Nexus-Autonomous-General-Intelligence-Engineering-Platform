from dataclasses import dataclass
from typing import Any

from services.api.app.models import ExecutionRequest
from services.api.app.services.execution import normalize_execution_result


@dataclass(frozen=True)
class ExecutionOutcome:
    success: bool
    result: dict[str, Any]
    output_bytes: int
    error_code: str | None = None
    failure_reason: str | None = None


class ExecutionBackend:
    """Explicit executor boundary; external plugin execution is fail-closed in Phase 13."""

    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        raise NotImplementedError


class FailClosedExecutor(ExecutionBackend):
    async def execute(self, request: ExecutionRequest) -> ExecutionOutcome:
        reason = (
            "No isolated artifact executor is enabled for this entrypoint; "
            "execution stopped before plugin code could run."
        )
        result = {"status": "blocked", "entrypoint": request.entrypoint}
        normalized, size = normalize_execution_result(
            result,
            max_output_bytes=request.max_output_bytes,
        )
        return ExecutionOutcome(
            success=False,
            result=normalized,
            output_bytes=size,
            error_code="executor_unavailable",
            failure_reason=reason,
        )

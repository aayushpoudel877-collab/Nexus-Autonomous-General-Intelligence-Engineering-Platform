import pytest

from services.api.app.models import ExecutionRequest
from services.execution.executor import FailClosedExecutor


@pytest.mark.asyncio
async def test_phase_13_worker_fails_closed_before_external_plugin_execution():
    request = ExecutionRequest(
        entrypoint="plugin.run",
        input_json={"hello": "world"},
        max_output_bytes=4096,
    )

    outcome = await FailClosedExecutor().execute(request)

    assert outcome.success is False
    assert outcome.error_code == "executor_unavailable"
    assert outcome.result["status"] == "blocked"
    assert outcome.output_bytes <= request.max_output_bytes


def test_phase_13_worker_package_is_importable():
    from services.execution.config import settings

    assert settings.worker_id
    assert settings.poll_seconds > 0
    assert settings.lease_seconds >= 5

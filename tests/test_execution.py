import pytest
from pydantic import ValidationError

from services.api.app.db.base import Base
from services.api.app.schemas.execution import ExecutionRequestCreate
from services.api.app.services.execution import (
    build_policy_snapshot,
    ensure_execution_transition,
    execution_lease_expiry,
    normalize_execution_policy,
    normalize_execution_result,
    normalize_failure_reason,
    should_retry_execution,
    validate_network_allowlist,
)


def test_phase_12_table_is_registered():
    assert "execution_requests" in Base.metadata.tables


def test_phase_12_routes_are_registered():
    from services.api.app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/execution/requests" in paths
    assert "/api/v1/execution/requests/{request_id}" in paths
    assert "/api/v1/execution/requests/{request_id}/cancel" in paths


def test_execution_policy_is_bounded():
    capabilities, allowlist, snapshot = normalize_execution_policy(
        capabilities=["dataset.read", "model.read", "dataset.read"],
        timeout_seconds=300,
        max_memory_mb=512,
        max_output_bytes=1_048_576,
        network_policy="allowlist",
        network_allowlist=["api.example.com", "api.example.com:443"],
    )

    assert capabilities == ["dataset.read", "model.read"]
    assert allowlist == ["api.example.com", "api.example.com:443"]
    assert snapshot["execution"]["sandbox_required"] is True
    assert snapshot["execution"]["artifact_verification_required"] is True
    assert snapshot["execution"]["artifact_verified"] is False


def test_execution_policy_rejects_network_without_allowlist_mode():
    with pytest.raises(ValueError):
        normalize_execution_policy(
            capabilities=["dataset.read"],
            timeout_seconds=300,
            max_memory_mb=512,
            max_output_bytes=1_048_576,
            network_policy="none",
            network_allowlist=["api.example.com"],
        )


def test_execution_policy_rejects_invalid_hosts():
    with pytest.raises(ValueError):
        validate_network_allowlist(["https://evil.example/path"])


def test_execution_lifecycle_allows_only_controlled_transitions():
    ensure_execution_transition("queued", "running")
    ensure_execution_transition("running", "succeeded")
    ensure_execution_transition("running", "failed")
    ensure_execution_transition("queued", "cancelled")

    with pytest.raises(ValueError):
        ensure_execution_transition("succeeded", "running")


def test_execution_schema_rejects_blank_identifiers():
    with pytest.raises(ValidationError):
        ExecutionRequestCreate(
            installation_id="00000000-0000-0000-0000-000000000000",
            idempotency_key="        ",
            entrypoint="plugin.run",
            capabilities=["dataset.read"],
        )

    with pytest.raises(ValidationError):
        ExecutionRequestCreate(
            installation_id="00000000-0000-0000-0000-000000000000",
            idempotency_key="request-123",
            entrypoint="   ",
            capabilities=["dataset.read"],
        )


def test_execution_schema_bounds_input_size():
    with pytest.raises(ValidationError):
        ExecutionRequestCreate(
            installation_id="00000000-0000-0000-0000-000000000000",
            idempotency_key="request-123",
            entrypoint="plugin.run",
            input_json={"payload": "x" * 66_000},
            capabilities=["dataset.read"],
        )


def test_policy_snapshot_is_explicit_and_reproducible():
    snapshot = build_policy_snapshot(
        capabilities=["dataset.read"],
        timeout_seconds=60,
        max_memory_mb=256,
        max_output_bytes=4096,
        network_policy="none",
        network_allowlist=[],
        provenance={
            "plugin_release_id": "release-1",
            "package_sha256": "a" * 64,
        },
    )
    assert snapshot == {
        "version": 2,
        "capabilities": ["dataset.read"],
        "limits": {
            "timeout_seconds": 60,
            "max_memory_mb": 256,
            "max_output_bytes": 4096,
        },
        "network": {"policy": "none", "allowlist": []},
        "provenance": {
            "plugin_release_id": "release-1",
            "package_sha256": "a" * 64,
        },
        "execution": {
            "sandbox_required": True,
            "artifact_verification_required": True,
            "secret_access_requires_external_reference": True,
            "artifact_verified": False,
        },
    }



def test_worker_lease_expiry_is_bounded():
    from datetime import datetime, timezone

    now = datetime(2026, 10, 3, 4, 0, tzinfo=timezone.utc)
    expiry = execution_lease_expiry(now=now, lease_seconds=30)
    assert (expiry - now).total_seconds() == 30


def test_worker_lease_result_is_bounded():
    result, size = normalize_execution_result(
        {"status": "ok", "value": "hello"},
        max_output_bytes=4096,
    )
    assert result["status"] == "ok"
    assert size > 0

    with pytest.raises(ValueError):
        normalize_execution_result({"value": "x" * 5000}, max_output_bytes=4096)


def test_worker_failures_are_normalized_and_retried_within_limit():
    assert normalize_failure_reason("  execution failed  ") == "execution failed"
    assert should_retry_execution(0) is True
    assert should_retry_execution(2) is True
    assert should_retry_execution(3) is False


def test_worker_lease_rejects_unsafe_duration():
    with pytest.raises(ValueError):
        execution_lease_expiry(lease_seconds=4)



def test_policy_snapshot_records_verified_artifact_state():
    snapshot = build_policy_snapshot(
        capabilities=["dataset.read"],
        timeout_seconds=60,
        max_memory_mb=256,
        max_output_bytes=4096,
        network_policy="none",
        network_allowlist=[],
        artifact_verified=True,
    )
    assert snapshot["version"] == 2
    assert snapshot["execution"]["artifact_verified"] is True

"""Policy and lifecycle rules for the controlled execution queue."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any


_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"running", "cancelled"},
    "running": {"succeeded", "failed", "cancelled"},
    "succeeded": set(),
    "failed": set(),
    "cancelled": set(),
}

MAX_TIMEOUT_SECONDS = 3_600
MAX_MEMORY_MB = 4_096
MAX_OUTPUT_BYTES = 16 * 1_024 * 1_024
MAX_CAPABILITIES = 16
MAX_SECRET_GRANTS = 8
MIN_SECRET_LEASE_SECONDS = 60
MAX_SECRET_LEASE_SECONDS = 7 * 24 * 60 * 60
MAX_INPUT_JSON_BYTES = 64 * 1_024
MAX_ALLOWLIST_ENTRIES = 20
MAX_EGRESS_REQUEST_BYTES = 128 * 1_024
MAX_EGRESS_RESPONSE_BYTES = 4 * 1_024 * 1_024
MAX_EGRESS_TIMEOUT_SECONDS = 15
NETWORK_CAPABILITY = "network.http"
SECRET_CAPABILITY = "secret.read"
WORKER_LEASE_SECONDS = 60
WORKER_POLL_SECONDS = 2
MAX_WORKER_ATTEMPTS = 3
MAX_FAILURE_REASON = 1_000

_HOST_PATTERN = re.compile(r"^[A-Za-z0-9.-]{1,253}(?::[0-9]{1,5})?$")


def ensure_execution_transition(current: str, requested: str) -> None:
    if requested == current:
        return
    if requested not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(
            f"Cannot change execution status from '{current}' to '{requested}'"
        )


def validate_network_allowlist(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        item = value.strip().lower()
        if not _HOST_PATTERN.fullmatch(item):
            raise ValueError("Network allowlist entries must be hostnames with optional ports")
        if ":" in item:
            host, port_text = item.rsplit(":", 1)
            if not 1 <= int(port_text) <= 65_535:
                raise ValueError("Network allowlist ports must be between 1 and 65535")
            if not host or host.startswith(".") or host.endswith("."):
                raise ValueError("Network allowlist hostnames are invalid")
        elif item.startswith(".") or item.endswith("."):
            raise ValueError("Network allowlist hostnames are invalid")
        if item not in normalized:
            normalized.append(item)
    if len(normalized) > MAX_ALLOWLIST_ENTRIES:
        raise ValueError(f"Network allowlist cannot contain more than {MAX_ALLOWLIST_ENTRIES} entries")
    return normalized


def build_policy_snapshot(
    *,
    capabilities: list[str],
    timeout_seconds: int,
    max_memory_mb: int,
    max_output_bytes: int,
    network_policy: str,
    network_allowlist: list[str],
    provenance: dict[str, str] | None = None,
    artifact_verified: bool = False,
    secret_grant_ids: list[str] | None = None,
    secret_grant_expires_at: dict[str, str] | None = None,
    secret_grant_ref_sha256: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "version": 6,
        "capabilities": list(capabilities),
        "limits": {
            "timeout_seconds": timeout_seconds,
            "max_memory_mb": max_memory_mb,
            "max_output_bytes": max_output_bytes,
        },
        "network": {
            "policy": network_policy,
            "allowlist": list(network_allowlist),
        },
        "execution": {
            "sandbox_required": True,
            "artifact_verification_required": True,
            "secret_access_requires_external_reference": True,
            "artifact_verified": artifact_verified,
            "network_mediation_required": network_policy == "allowlist",
            "secret_mediation_required": bool(secret_grant_ids),
        },
        "egress": {
            "mode": "unix_socket_broker" if network_policy == "allowlist" else "disabled",
            "max_request_bytes": MAX_EGRESS_REQUEST_BYTES,
            "max_response_bytes": MAX_EGRESS_RESPONSE_BYTES,
            "timeout_seconds": min(timeout_seconds, MAX_EGRESS_TIMEOUT_SECONDS),
            "max_redirects": 0,
        },
        "secrets": {
            "mode": "unix_socket_broker" if secret_grant_ids else "disabled",
            "grant_ids": list(secret_grant_ids or []),
            "grant_expires_at": dict(secret_grant_expires_at or {}),
            "grant_reference_sha256": dict(secret_grant_ref_sha256 or {}),
            "max_grants": MAX_SECRET_GRANTS,
            "max_value_bytes": 64 * 1024,
            "cache": "none",
            "lease_min_seconds": MIN_SECRET_LEASE_SECONDS,
            "lease_max_seconds": MAX_SECRET_LEASE_SECONDS,
        },
        "provenance": dict(provenance or {}),
    }


def normalize_execution_policy(
    *,
    capabilities: list[str],
    timeout_seconds: int,
    max_memory_mb: int,
    max_output_bytes: int,
    network_policy: str,
    network_allowlist: list[str],
    provenance: dict[str, str] | None = None,
    artifact_verified: bool = False,
    secret_grant_ids: list[str] | None = None,
    secret_grant_expires_at: dict[str, str] | None = None,
    secret_grant_ref_sha256: dict[str, str] | None = None,
) -> tuple[list[str], list[str], dict[str, Any]]:
    capabilities = list(dict.fromkeys(capabilities))
    secret_grant_ids = list(dict.fromkeys(secret_grant_ids or []))
    secret_grant_expires_at = dict(secret_grant_expires_at or {})
    secret_grant_ref_sha256 = dict(secret_grant_ref_sha256 or {})
    if len(secret_grant_ids) > MAX_SECRET_GRANTS:
        raise ValueError(f"Execution requests cannot use more than {MAX_SECRET_GRANTS} secret grants")
    if secret_grant_ids and SECRET_CAPABILITY not in capabilities:
        raise ValueError(f"Secret-enabled executions require the '{SECRET_CAPABILITY}' capability")
    if SECRET_CAPABILITY in capabilities and not secret_grant_ids:
        raise ValueError(f"The '{SECRET_CAPABILITY}' capability requires at least one approved secret grant")
    if set(secret_grant_expires_at) != set(secret_grant_ids):
        raise ValueError("Secret grant expiration metadata must match the requested secret grants")
    if set(secret_grant_ref_sha256) != set(secret_grant_ids):
        raise ValueError("Secret grant reference fingerprints must match the requested secret grants")
    if any(not isinstance(value, str) or not value for value in secret_grant_expires_at.values()):
        raise ValueError("Secret grant expiration metadata must contain ISO timestamps")
    if any(not isinstance(value, str) or len(value) != 64 for value in secret_grant_ref_sha256.values()):
        raise ValueError("Secret grant reference fingerprints must be SHA-256 hex values")
    if not capabilities or len(capabilities) > MAX_CAPABILITIES:
        raise ValueError(
            f"Execution requests require 1-{MAX_CAPABILITIES} capabilities"
        )
    if timeout_seconds < 1 or timeout_seconds > MAX_TIMEOUT_SECONDS:
        raise ValueError(
            f"timeout_seconds must be between 1 and {MAX_TIMEOUT_SECONDS}"
        )
    if max_memory_mb < 64 or max_memory_mb > MAX_MEMORY_MB:
        raise ValueError(f"max_memory_mb must be between 64 and {MAX_MEMORY_MB}")
    if max_output_bytes < 4_096 or max_output_bytes > MAX_OUTPUT_BYTES:
        raise ValueError(
            f"max_output_bytes must be between 4096 and {MAX_OUTPUT_BYTES}"
        )
    if network_policy not in {"none", "allowlist"}:
        raise ValueError("network_policy must be 'none' or 'allowlist'")
    if network_policy == "none" and network_allowlist:
        raise ValueError("A network allowlist is only valid with network_policy='allowlist'")
    normalized_allowlist = validate_network_allowlist(network_allowlist)
    if network_policy == "allowlist" and not normalized_allowlist:
        raise ValueError("Network-enabled executions require at least one allowlist entry")
    if network_policy == "allowlist" and NETWORK_CAPABILITY not in capabilities:
        raise ValueError(
            f"Network-enabled executions require the '{NETWORK_CAPABILITY}' capability"
        )
    snapshot = build_policy_snapshot(
        capabilities=capabilities,
        timeout_seconds=timeout_seconds,
        max_memory_mb=max_memory_mb,
        max_output_bytes=max_output_bytes,
        network_policy=network_policy,
        network_allowlist=normalized_allowlist,
        provenance=provenance,
        artifact_verified=artifact_verified,
        secret_grant_ids=secret_grant_ids,
        secret_grant_expires_at=secret_grant_expires_at,
        secret_grant_ref_sha256=secret_grant_ref_sha256,
    )
    return capabilities, normalized_allowlist, snapshot



def execution_lease_expiry(
    *,
    now: datetime | None = None,
    lease_seconds: int = WORKER_LEASE_SECONDS,
) -> datetime:
    if lease_seconds < 5 or lease_seconds > 600:
        raise ValueError("Worker lease must be between 5 and 600 seconds")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current + timedelta(seconds=lease_seconds)


def normalize_execution_result(
    result: dict[str, Any],
    *,
    max_output_bytes: int,
) -> tuple[dict[str, Any], int]:
    if not isinstance(result, dict):
        raise TypeError("Execution results must be JSON objects")
    encoded = json.dumps(
        result,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    if len(encoded) > max_output_bytes:
        raise ValueError("Execution result exceeds the request output limit")
    return result, len(encoded)


def normalize_failure_reason(reason: str) -> str:
    normalized = reason.strip()
    return normalized[:MAX_FAILURE_REASON]


def should_retry_execution(attempt_count: int) -> bool:
    return 0 <= attempt_count < MAX_WORKER_ATTEMPTS

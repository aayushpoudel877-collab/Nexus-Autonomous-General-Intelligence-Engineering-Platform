"""Fail-closed admission checks for the isolated plugin runtime."""

from dataclasses import dataclass
from typing import Any

from services.api.app.services.artifact_store import ArtifactStore


@dataclass(frozen=True)
class SandboxAdmission:
    artifact_digest: str
    artifact_size_bytes: int
    network_policy: str
    network_allowlist: list[str]
    sandbox_required: bool
    egress_required: bool
    secret_grant_ids: list[str]
    secret_required: bool


def admit_verified_artifact(
    *,
    policy_snapshot: dict[str, Any],
    artifact_store: ArtifactStore,
) -> SandboxAdmission:
    if not isinstance(policy_snapshot, dict):
        raise TypeError("Execution policy snapshot is missing")
    version = policy_snapshot.get("version")
    if version not in {2, 3, 4}:
        raise ValueError("Execution policy snapshot version is unsupported")
    execution = policy_snapshot.get("execution")
    provenance = policy_snapshot.get("provenance")
    limits = policy_snapshot.get("limits")

    if not isinstance(execution, dict) or execution.get("sandbox_required") is not True:
        raise ValueError("Execution policy does not require sandboxing")
    if execution.get("artifact_verification_required") is not True:
        raise ValueError("Execution policy does not require artifact verification")
    if execution.get("artifact_verified") is not True:
        raise ValueError("Execution artifact has not been cryptographically verified")
    if not isinstance(provenance, dict):
        raise TypeError("Execution policy provenance is missing")
    if not isinstance(limits, dict):
        raise TypeError("Execution policy limits are missing")

    artifact_digest = provenance.get("package_sha256", "")
    storage_key = provenance.get("artifact_storage_key", "")
    if artifact_digest != storage_key or len(artifact_digest) != 64:
        raise ValueError("Execution artifact storage identity does not match its digest")

    artifact = artifact_store.read_verified(storage_key)
    expected_size = int(provenance.get("artifact_size_bytes", "0"))
    if expected_size <= 0 or len(artifact) != expected_size:
        raise ValueError("Stored artifact size does not match frozen execution provenance")

    network = policy_snapshot.get("network")
    if not isinstance(network, dict):
        raise TypeError("Execution network policy is missing")
    network_policy = network.get("policy")
    allowlist = network.get("allowlist")
    if not isinstance(allowlist, list) or any(not isinstance(item, str) for item in allowlist):
        raise TypeError("Execution network allowlist is invalid")
    if network_policy not in {"none", "allowlist"}:
        raise ValueError("Execution network policy is unsupported")
    egress_required = network_policy == "allowlist"
    if egress_required:
        if version < 3:
            raise ValueError("Network-enabled execution requires a Phase 18 policy snapshot")
        egress = policy_snapshot.get("egress")
        if not isinstance(egress, dict) or egress.get("mode") != "unix_socket_broker":
            raise ValueError("Network-enabled execution requires mediated egress")
        if not allowlist:
            raise ValueError("Network-enabled execution requires a non-empty allowlist")
    elif version >= 3:
        egress = policy_snapshot.get("egress")
        if not isinstance(egress, dict) or egress.get("mode") != "disabled":
            raise ValueError("Network-disabled execution has an invalid egress mode")

    secret_grant_ids: list[str] = []
    secret_required = False
    if version >= 4:
        secrets = policy_snapshot.get("secrets")
        if not isinstance(secrets, dict):
            raise ValueError("Execution secret policy is missing")
        mode = secrets.get("mode")
        grant_ids = secrets.get("grant_ids")
        if not isinstance(grant_ids, list) or any(not isinstance(item, str) for item in grant_ids):
            raise TypeError("Execution secret grant IDs are invalid")
        if len(grant_ids) > 8:
            raise ValueError("Execution requests cannot use more than 8 secret grants")
        if mode == "unix_socket_broker":
            if not grant_ids:
                raise ValueError("Secret broker mode requires at least one grant")
            secret_required = True
            secret_grant_ids = list(dict.fromkeys(grant_ids))
        elif mode != "disabled" or grant_ids:
            raise ValueError("Execution secret policy is invalid")

    return SandboxAdmission(
        artifact_digest=artifact_digest,
        artifact_size_bytes=len(artifact),
        network_policy=network_policy,
        network_allowlist=list(allowlist),
        sandbox_required=True,
        egress_required=egress_required,
        secret_grant_ids=secret_grant_ids,
        secret_required=secret_required,
    )

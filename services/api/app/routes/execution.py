from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import require_api_key_scopes
from ..db.session import get_db
from ..models import (
    DeveloperApiKey,
    PluginInstallation,
    PluginRegistration,
    PluginRelease,
    PluginTrustRoot,
    ExecutionRequest,
)
from ..schemas.execution import ExecutionCancel, ExecutionRequestCreate, ExecutionRequestRead
from ..services.audit import record_audit
from ..services.execution import ensure_execution_transition, normalize_execution_policy

router = APIRouter(prefix="/execution", tags=["controlled-execution"])


async def _approved_installation(
    db: AsyncSession,
    installation_id: UUID,
    organization_id: UUID,
) -> tuple[PluginInstallation, PluginRelease, PluginRegistration]:
    row = await db.execute(
        select(PluginInstallation, PluginRelease, PluginRegistration)
        .join(PluginRelease, PluginInstallation.plugin_release_id == PluginRelease.id)
        .join(PluginRegistration, PluginRelease.plugin_id == PluginRegistration.id)
        .join(
            PluginTrustRoot,
            (PluginTrustRoot.organization_id == PluginRegistration.organization_id)
            & (PluginTrustRoot.key_id == PluginRelease.verification_key_id),
        )
        .where(
            PluginInstallation.id == installation_id,
            PluginInstallation.organization_id == organization_id,
            PluginInstallation.status == "approved",
            PluginRelease.status == "verified",
            PluginRelease.artifact_verified_at.is_not(None),
            PluginRelease.verification_key_id == PluginTrustRoot.key_id,
            PluginTrustRoot.status == "active",
            PluginRegistration.status == "active",
        )
    )
    result = row.first()
    if result is None:
        raise HTTPException(
            status_code=409,
            detail="A verified and approved plugin installation is required",
        )
    return result


def _manifest_capabilities(manifest: dict) -> set[str]:
    capabilities = manifest.get("capabilities", [])
    if not isinstance(capabilities, list) or any(
        not isinstance(item, str) for item in capabilities
    ):
        raise HTTPException(
            status_code=409,
            detail="Plugin manifest has no valid capabilities declaration",
        )
    return set(capabilities)


def _manifest_entrypoints(manifest: dict) -> set[str]:
    entrypoints = manifest.get("entrypoints", [])
    if not isinstance(entrypoints, list) or any(
        not isinstance(item, str) for item in entrypoints
    ):
        raise HTTPException(
            status_code=409,
            detail="Plugin manifest has no valid entrypoints declaration",
        )
    return set(entrypoints)


@router.get("/requests", response_model=list[ExecutionRequestRead])
async def list_execution_requests(
    api_key: DeveloperApiKey = Depends(require_api_key_scopes("plugin:execute")),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(ExecutionRequest)
        .where(ExecutionRequest.organization_id == api_key.organization_id)
        .order_by(ExecutionRequest.created_at.desc())
        .limit(100)
    )
    return list(rows.all())


@router.post("/requests", response_model=ExecutionRequestRead, status_code=201)
async def create_execution_request(
    payload: ExecutionRequestCreate,
    request: Request,
    api_key: DeveloperApiKey = Depends(require_api_key_scopes("plugin:execute")),
    db: AsyncSession = Depends(get_db),
):
    installation, release, plugin = await _approved_installation(
        db,
        payload.installation_id,
        api_key.organization_id,
    )

    try:
        requested_capabilities, network_allowlist, policy_snapshot = (
            normalize_execution_policy(
                capabilities=payload.capabilities,
                timeout_seconds=payload.timeout_seconds,
                max_memory_mb=payload.max_memory_mb,
                max_output_bytes=payload.max_output_bytes,
                network_policy=payload.network_policy,
                network_allowlist=payload.network_allowlist,
                provenance={
                    "plugin_id": str(plugin.id),
                    "plugin_release_id": str(release.id),
                    "plugin_version": release.version,
                    "package_sha256": release.package_sha256,
                    "manifest_sha256": release.manifest_sha256,
                    "signer": release.signer,
                    "verification_key_id": release.verification_key_id or "",
                    "verification_method": release.verification_method or "",
                },
                artifact_verified=bool(release.artifact_verified_at),
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    approved_capabilities = set(installation.approved_scopes or [])
    if not isinstance(release.manifest_snapshot, dict):
        raise HTTPException(
            status_code=409,
            detail="Plugin release does not contain a frozen manifest snapshot",
        )
    declared_capabilities = _manifest_capabilities(release.manifest_snapshot)
    if not set(requested_capabilities).issubset(approved_capabilities):
        raise HTTPException(
            status_code=422,
            detail="Execution capabilities must be a subset of the approved installation scopes",
        )
    if not set(requested_capabilities).issubset(declared_capabilities):
        raise HTTPException(
            status_code=422,
            detail="Execution capabilities must be declared by the plugin manifest",
        )

    declared_entrypoints = _manifest_entrypoints(release.manifest_snapshot)
    if payload.entrypoint not in declared_entrypoints:
        raise HTTPException(
            status_code=422,
            detail="Execution entrypoint is not declared by the plugin manifest",
        )

    existing = await db.scalar(
        select(ExecutionRequest).where(
            ExecutionRequest.organization_id == api_key.organization_id,
            ExecutionRequest.idempotency_key == payload.idempotency_key,
        )
    )
    if existing:
        compatible = (
            existing.installation_id == installation.id
            and existing.entrypoint == payload.entrypoint
            and existing.input_json == payload.input_json
            and existing.capabilities == requested_capabilities
            and existing.timeout_seconds == payload.timeout_seconds
            and existing.max_memory_mb == payload.max_memory_mb
            and existing.max_output_bytes == payload.max_output_bytes
            and existing.network_policy == payload.network_policy
            and existing.network_allowlist == network_allowlist
        )
        if not compatible:
            raise HTTPException(
                status_code=409,
                detail="Idempotency key has already been used with a different execution request",
            )
        return existing

    request_record = ExecutionRequest(
        organization_id=api_key.organization_id,
        installation_id=installation.id,
        requested_by_user_id=api_key.created_by_user_id,
        idempotency_key=payload.idempotency_key,
        entrypoint=payload.entrypoint,
        input_json=payload.input_json,
        capabilities=requested_capabilities,
        timeout_seconds=payload.timeout_seconds,
        max_memory_mb=payload.max_memory_mb,
        max_output_bytes=payload.max_output_bytes,
        network_policy=payload.network_policy,
        network_allowlist=network_allowlist,
        policy_snapshot=policy_snapshot,
        status="queued",
    )
    try:
        async with db.begin_nested():
            db.add(request_record)
            await db.flush()
    except IntegrityError:
        existing = await db.scalar(
            select(ExecutionRequest).where(
                ExecutionRequest.organization_id == api_key.organization_id,
                ExecutionRequest.idempotency_key == payload.idempotency_key,
            )
        )
        if existing is None:
            raise
        compatible = (
            existing.installation_id == installation.id
            and existing.entrypoint == payload.entrypoint
            and existing.input_json == payload.input_json
            and existing.capabilities == requested_capabilities
            and existing.timeout_seconds == payload.timeout_seconds
            and existing.max_memory_mb == payload.max_memory_mb
            and existing.max_output_bytes == payload.max_output_bytes
            and existing.network_policy == payload.network_policy
            and existing.network_allowlist == network_allowlist
        )
        if not compatible:
            raise HTTPException(
                status_code=409,
                detail="Idempotency key has already been used with a different execution request",
            )
        return existing

    await record_audit(
        db,
        action="execution.requested",
        resource_type="execution_request",
        actor_user_id=api_key.created_by_user_id,
        organization_id=api_key.organization_id,
        resource_id=str(request_record.id),
        detail={
            "installation_id": str(installation.id),
            "release_id": str(release.id),
            "plugin_id": str(plugin.id),
            "entrypoint": request_record.entrypoint,
            "capabilities": requested_capabilities,
        },
        request_id=getattr(request.state, "request_id", None),
    )
    await db.commit()
    await db.refresh(request_record)
    return request_record


@router.get("/requests/{request_id}", response_model=ExecutionRequestRead)
async def get_execution_request(
    request_id: UUID,
    api_key: DeveloperApiKey = Depends(require_api_key_scopes("plugin:execute")),
    db: AsyncSession = Depends(get_db),
):
    record = await db.scalar(
        select(ExecutionRequest).where(
            ExecutionRequest.id == request_id,
            ExecutionRequest.organization_id == api_key.organization_id,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Execution request not found")
    return record


@router.post("/requests/{request_id}/cancel", response_model=ExecutionRequestRead)
async def cancel_execution_request(
    request_id: UUID,
    payload: ExecutionCancel,
    request: Request,
    api_key: DeveloperApiKey = Depends(require_api_key_scopes("plugin:execute")),
    db: AsyncSession = Depends(get_db),
):
    record = await db.scalar(
        select(ExecutionRequest).where(
            ExecutionRequest.id == request_id,
            ExecutionRequest.organization_id == api_key.organization_id,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Execution request not found")
    if record.status not in {"queued", "running"}:
        raise HTTPException(
            status_code=409,
            detail="Only queued or running executions can be cancelled",
        )

    ensure_execution_transition(record.status, "cancelled")
    record.status = "cancelled"
    record.worker_id = None
    record.lease_expires_at = None
    record.heartbeat_at = None
    record.error_code = "cancelled"
    record.failure_reason = payload.reason.strip()
    record.finished_at = datetime.now(timezone.utc)
    await record_audit(
        db,
        action="execution.cancelled",
        resource_type="execution_request",
        actor_user_id=api_key.created_by_user_id,
        organization_id=api_key.organization_id,
        resource_id=str(record.id),
        detail={"reason": record.failure_reason},
        request_id=getattr(request.state, "request_id", None),
    )
    await db.commit()
    await db.refresh(record)
    return record

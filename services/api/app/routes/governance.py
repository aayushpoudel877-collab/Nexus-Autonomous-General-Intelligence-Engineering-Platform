from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import (
    get_membership,
    require_api_key_scopes,
    require_roles,
)
from ..db.session import get_db
from ..models import (
    IntegrationConnection,
    PluginInstallation,
    PluginRegistration,
    PluginRelease,
    User,
    DeveloperApiKey,
)
from ..schemas.integrations import (
    IntegrationCreate,
    IntegrationRead,
    IntegrationUpdate,
    PluginInstallationApproval,
    PluginInstallationCreate,
    PluginInstallationRead,
    PluginReleaseCreate,
    PluginReleaseRead,
    PluginReleaseVerification,
)
from ..services.audit import record_audit

router = APIRouter(prefix="/governance", tags=["ecosystem-governance"])


async def _plugin_for_release(
    db: AsyncSession,
    plugin_id: UUID,
    organization_id: UUID,
) -> PluginRegistration:
    plugin = await db.scalar(
        select(PluginRegistration).where(
            PluginRegistration.id == plugin_id,
            PluginRegistration.organization_id == organization_id,
        )
    )
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return plugin


async def _installation_for_org(
    db: AsyncSession,
    installation_id: UUID,
    organization_id: UUID,
) -> PluginInstallation:
    installation = await db.scalar(
        select(PluginInstallation).where(
            PluginInstallation.id == installation_id,
            PluginInstallation.organization_id == organization_id,
        )
    )
    if installation is None:
        raise HTTPException(status_code=404, detail="Plugin installation not found")
    return installation


@router.get("/integrations", response_model=list[IntegrationRead])
async def list_integrations(
    api_key: DeveloperApiKey = Depends(require_api_key_scopes("integration:read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(IntegrationConnection)
        .where(IntegrationConnection.organization_id == api_key.organization_id)
        .order_by(IntegrationConnection.created_at.desc())
    )
    return list(rows.all())


@router.post("/integrations", response_model=IntegrationRead, status_code=201)
async def create_integration(
    payload: IntegrationCreate,
    request: Request,
    api_key: DeveloperApiKey = Depends(require_api_key_scopes("integration:write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.organization_id == api_key.organization_id,
            IntegrationConnection.provider == payload.provider,
            IntegrationConnection.name == payload.name,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="An integration with this provider and name already exists")

    integration = IntegrationConnection(
        organization_id=api_key.organization_id,
        created_by_user_id=api_key.created_by_user_id,
        **payload.model_dump(),
    )
    db.add(integration)
    await db.flush()
    await record_audit(
        db,
        action="developer.integration.created",
        resource_type="integration",
        actor_user_id=api_key.created_by_user_id,
        organization_id=api_key.organization_id,
        resource_id=str(integration.id),
        detail={"provider": integration.provider, "name": integration.name},
        request_id=getattr(request.state, "request_id", None),
    )
    await db.commit()
    await db.refresh(integration)
    return integration


@router.patch("/integrations/{integration_id}", response_model=IntegrationRead)
async def update_integration(
    integration_id: UUID,
    payload: IntegrationUpdate,
    request: Request,
    api_key: DeveloperApiKey = Depends(require_api_key_scopes("integration:write")),
    db: AsyncSession = Depends(get_db),
):
    integration = await db.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.id == integration_id,
            IntegrationConnection.organization_id == api_key.organization_id,
        )
    )
    if integration is None:
        raise HTTPException(status_code=404, detail="Integration not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(integration, field, value)
    if updates:
        await record_audit(
            db,
            action="developer.integration.updated",
            resource_type="integration",
            actor_user_id=api_key.created_by_user_id,
            organization_id=api_key.organization_id,
            resource_id=str(integration.id),
            detail={"fields": sorted(updates)},
            request_id=getattr(request.state, "request_id", None),
        )
        await db.commit()
        await db.refresh(integration)
    return integration


@router.get("/plugins/{plugin_id}/releases", response_model=list[PluginReleaseRead])
async def list_releases(
    plugin_id: UUID,
    api_key: DeveloperApiKey = Depends(require_api_key_scopes("plugin:read")),
    db: AsyncSession = Depends(get_db),
):
    await _plugin_for_release(db, plugin_id, api_key.organization_id)
    rows = await db.scalars(
        select(PluginRelease)
        .where(PluginRelease.plugin_id == plugin_id)
        .order_by(PluginRelease.created_at.desc())
    )
    return list(rows.all())


@router.post("/plugins/{plugin_id}/releases", response_model=PluginReleaseRead, status_code=201)
async def create_release(
    plugin_id: UUID,
    payload: PluginReleaseCreate,
    request: Request,
    api_key: DeveloperApiKey = Depends(require_api_key_scopes("plugin:release")),
    db: AsyncSession = Depends(get_db),
):
    plugin = await _plugin_for_release(db, plugin_id, api_key.organization_id)
    if plugin.status != "active":
        raise HTTPException(status_code=409, detail="Disabled plugins cannot publish releases")

    existing = await db.scalar(
        select(PluginRelease).where(
            PluginRelease.plugin_id == plugin.id,
            PluginRelease.version == payload.version,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="A release with this plugin version already exists")

    release = PluginRelease(
        plugin_id=plugin.id,
        created_by_user_id=api_key.created_by_user_id,
        **payload.model_dump(),
    )
    db.add(release)
    await db.flush()
    await record_audit(
        db,
        action="developer.plugin_release.created",
        resource_type="plugin_release",
        actor_user_id=api_key.created_by_user_id,
        organization_id=api_key.organization_id,
        resource_id=str(release.id),
        detail={"plugin_id": str(plugin.id), "version": release.version},
        request_id=getattr(request.state, "request_id", None),
    )
    await db.commit()
    await db.refresh(release)
    return release


@router.post("/plugin-releases/{release_id}/verify", response_model=PluginReleaseRead)
async def verify_release(
    release_id: UUID,
    payload: PluginReleaseVerification,
    request: Request,
    user: User = Depends(require_roles("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    release = await db.scalar(
        select(PluginRelease)
        .join(PluginRegistration, PluginRelease.plugin_id == PluginRegistration.id)
        .where(
            PluginRelease.id == release_id,
            PluginRegistration.organization_id == membership.organization_id,
        )
    )
    if release is None:
        raise HTTPException(status_code=404, detail="Plugin release not found")

    if release.status != "pending":
        raise HTTPException(status_code=409, detail="Plugin release has already been reviewed")

    release.status = payload.status
    release.verification_note = payload.note.strip()
    release.verified_by_user_id = user.id
    release.verified_at = datetime.now(timezone.utc)
    await record_audit(
        db,
        action="developer.plugin_release.reviewed",
        resource_type="plugin_release",
        actor_user_id=user.id,
        organization_id=membership.organization_id,
        resource_id=str(release.id),
        detail={"status": release.status, "version": release.version},
        request_id=getattr(request.state, "request_id", None),
    )
    await db.commit()
    await db.refresh(release)
    return release


@router.get("/plugin-installations", response_model=list[PluginInstallationRead])
async def list_installations(
    api_key: DeveloperApiKey = Depends(require_api_key_scopes("plugin:read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(PluginInstallation)
        .where(PluginInstallation.organization_id == api_key.organization_id)
        .order_by(PluginInstallation.created_at.desc())
    )
    return list(rows.all())


@router.post("/plugin-installations", response_model=PluginInstallationRead, status_code=201)
async def request_installation(
    payload: PluginInstallationCreate,
    request: Request,
    api_key: DeveloperApiKey = Depends(require_api_key_scopes("plugin:install")),
    db: AsyncSession = Depends(get_db),
):
    release_and_plugin = await db.execute(
        select(PluginRelease, PluginRegistration)
        .join(PluginRegistration, PluginRelease.plugin_id == PluginRegistration.id)
        .where(
            PluginRelease.id == payload.plugin_release_id,
            PluginRegistration.status == "active",
            PluginRegistration.organization_id == api_key.organization_id,
        )
    )
    row = release_and_plugin.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Plugin release not found")
    release, plugin = row
    if release.status != "verified":
        raise HTTPException(status_code=409, detail="Only verified plugin releases can be installed")

    declared_capabilities = plugin.manifest.get("capabilities", [])
    if not isinstance(declared_capabilities, list) or any(
        not isinstance(capability, str) for capability in declared_capabilities
    ):
        raise HTTPException(status_code=409, detail="Plugin manifest has no valid capabilities declaration")
    requested_scopes = list(dict.fromkeys(payload.requested_scopes))
    if not set(requested_scopes).issubset(set(declared_capabilities)):
        raise HTTPException(
            status_code=422,
            detail="Requested plugin scopes must be declared by the plugin manifest",
        )

    existing = await db.scalar(
        select(PluginInstallation).where(
            PluginInstallation.organization_id == api_key.organization_id,
            PluginInstallation.plugin_release_id == release.id,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="This plugin release already has an installation request")

    installation = PluginInstallation(
        organization_id=api_key.organization_id,
        plugin_release_id=release.id,
        created_by_user_id=api_key.created_by_user_id,
        requested_scopes=requested_scopes,
    )
    db.add(installation)
    await db.flush()
    await record_audit(
        db,
        action="developer.plugin_installation.requested",
        resource_type="plugin_installation",
        actor_user_id=api_key.created_by_user_id,
        organization_id=api_key.organization_id,
        resource_id=str(installation.id),
        detail={"release_id": str(release.id), "requested_scopes": installation.requested_scopes},
        request_id=getattr(request.state, "request_id", None),
    )
    await db.commit()
    await db.refresh(installation)
    return installation


@router.post("/plugin-installations/{installation_id}/approve", response_model=PluginInstallationRead)
async def approve_installation(
    installation_id: UUID,
    payload: PluginInstallationApproval,
    request: Request,
    user: User = Depends(require_roles("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    installation = await _installation_for_org(
        db, installation_id, membership.organization_id
    )
    if installation.status != "requested":
        raise HTTPException(status_code=409, detail="Only requested installations can be reviewed")

    release = await db.get(PluginRelease, installation.plugin_release_id)
    if release is None or release.status != "verified":
        raise HTTPException(status_code=409, detail="A verified release is required before approval")

    approved_scopes = list(dict.fromkeys(payload.approved_scopes))
    requested = set(installation.requested_scopes or [])
    if not set(approved_scopes).issubset(requested):
        raise HTTPException(status_code=422, detail="Approved scopes must be a subset of requested scopes")

    installation.status = payload.status
    installation.approved_scopes = approved_scopes if payload.status == "approved" else []
    installation.approval_note = payload.note.strip()
    installation.approved_by_user_id = user.id
    installation.approved_at = datetime.now(timezone.utc)
    await record_audit(
        db,
        action="developer.plugin_installation.reviewed",
        resource_type="plugin_installation",
        actor_user_id=user.id,
        organization_id=membership.organization_id,
        resource_id=str(installation.id),
        detail={"status": installation.status, "approved_scopes": installation.approved_scopes},
        request_id=getattr(request.state, "request_id", None),
    )
    await db.commit()
    await db.refresh(installation)
    return installation

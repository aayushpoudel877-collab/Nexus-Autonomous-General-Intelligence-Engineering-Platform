from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import (
    get_developer_api_key,
    get_membership,
    require_api_key_scopes,
    require_roles,
)
from ..db.session import get_db
from ..models import DeveloperApiKey, PluginRegistration, User
from ..schemas.ecosystem import (
    DeveloperApiKeyCreated,
    DeveloperApiKeyCreate,
    DeveloperApiKeyRead,
    DeveloperIdentity,
    PluginCreate,
    PluginRead,
    PluginUpdate,
)
from ..services.audit import record_audit
from ..services.ecosystem import generate_api_key, normalize_scopes

router = APIRouter(prefix="/developer", tags=["developer-platform"])


@router.get("/api-keys", response_model=list[DeveloperApiKeyRead])
async def list_api_keys(
    user: User = Depends(require_roles("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    rows = await db.scalars(
        select(DeveloperApiKey)
        .where(DeveloperApiKey.organization_id == membership.organization_id)
        .order_by(DeveloperApiKey.created_at.desc())
    )
    return list(rows.all())


@router.post("/api-keys", response_model=DeveloperApiKeyCreated, status_code=201)
async def create_api_key(
    payload: DeveloperApiKeyCreate,
    request: Request,
    user: User = Depends(require_roles("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    if payload.expires_at is not None and payload.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="API key expiry must be in the future")
    try:
        scopes = normalize_scopes(payload.scopes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    secret, prefix, digest = generate_api_key()
    key = DeveloperApiKey(
        organization_id=membership.organization_id,
        created_by_user_id=user.id,
        name=payload.name,
        key_prefix=prefix,
        key_hash=digest,
        scopes=scopes,
        expires_at=payload.expires_at,
    )
    db.add(key)
    await db.flush()
    await record_audit(
        db,
        action="developer.api_key.created",
        resource_type="developer_api_key",
        actor_user_id=user.id,
        organization_id=membership.organization_id,
        resource_id=str(key.id),
        detail={"name": key.name, "key_prefix": key.key_prefix, "scopes": scopes},
        request_id=getattr(request.state, "request_id", None),
    )
    await db.commit()
    await db.refresh(key)
    return DeveloperApiKeyCreated.model_validate(key).model_copy(update={"secret": secret})


@router.post("/api-keys/{key_id}/revoke", response_model=DeveloperApiKeyRead)
async def revoke_api_key(
    key_id: UUID,
    request: Request,
    user: User = Depends(require_roles("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    key = await db.scalar(
        select(DeveloperApiKey).where(
            DeveloperApiKey.id == key_id,
            DeveloperApiKey.organization_id == membership.organization_id,
        )
    )
    if key is None:
        raise HTTPException(status_code=404, detail="Developer API key not found")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(timezone.utc)
        await record_audit(
            db,
            action="developer.api_key.revoked",
            resource_type="developer_api_key",
            actor_user_id=user.id,
            organization_id=membership.organization_id,
            resource_id=str(key.id),
            detail={"key_prefix": key.key_prefix},
            request_id=getattr(request.state, "request_id", None),
        )
        await db.commit()
        await db.refresh(key)
    return key


@router.get("/whoami", response_model=DeveloperIdentity)
async def whoami(
    api_key: DeveloperApiKey = Depends(require_api_key_scopes("developer:read")),
):
    return DeveloperIdentity(
        organization_id=api_key.organization_id,
        key_id=api_key.id,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes or [],
        expires_at=api_key.expires_at,
    )


@router.get("/plugins", response_model=list[PluginRead])
async def list_plugins(
    api_key: DeveloperApiKey = Depends(require_api_key_scopes("plugin:read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(PluginRegistration)
        .where(PluginRegistration.organization_id == api_key.organization_id)
        .order_by(PluginRegistration.created_at.desc())
    )
    return list(rows.all())


@router.post("/plugins", response_model=PluginRead, status_code=201)
async def create_plugin(
    payload: PluginCreate,
    request: Request,
    api_key: DeveloperApiKey = Depends(require_api_key_scopes("plugin:write")),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.scalar(
        select(PluginRegistration).where(
            PluginRegistration.organization_id == api_key.organization_id,
            PluginRegistration.slug == payload.slug,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="A plugin with this slug already exists")

    plugin = PluginRegistration(
        organization_id=api_key.organization_id,
        created_by_user_id=api_key.created_by_user_id,
        **payload.model_dump(),
    )
    db.add(plugin)
    await db.flush()
    await record_audit(
        db,
        action="developer.plugin.created",
        resource_type="plugin",
        actor_user_id=api_key.created_by_user_id,
        organization_id=api_key.organization_id,
        resource_id=str(plugin.id),
        detail={"slug": plugin.slug, "version": plugin.version},
        request_id=getattr(request.state, "request_id", None),
    )
    await db.commit()
    await db.refresh(plugin)
    return plugin


@router.patch("/plugins/{plugin_id}", response_model=PluginRead)
async def update_plugin(
    plugin_id: UUID,
    payload: PluginUpdate,
    request: Request,
    api_key: DeveloperApiKey = Depends(require_api_key_scopes("plugin:write")),
    db: AsyncSession = Depends(get_db),
):
    plugin = await db.scalar(
        select(PluginRegistration).where(
            PluginRegistration.id == plugin_id,
            PluginRegistration.organization_id == api_key.organization_id,
        )
    )
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(plugin, field, value)
    if updates:
        await record_audit(
            db,
            action="developer.plugin.updated",
            resource_type="plugin",
            actor_user_id=api_key.created_by_user_id,
            organization_id=api_key.organization_id,
            resource_id=str(plugin.id),
            detail={"fields": sorted(updates)},
            request_id=getattr(request.state, "request_id", None),
        )
        await db.commit()
        await db.refresh(plugin)
    return plugin

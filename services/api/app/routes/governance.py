import base64
import binascii
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
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
    PluginTrustRoot,
    SecretGrant,
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
from ..schemas.secrets import SecretGrantApproval, SecretGrantCreate, SecretGrantRead
from ..schemas.artifacts import (
    PluginArtifactVerification,
    PluginTrustRootCreate,
    PluginTrustRootRead,
)
from ..services.artifact_verification import MAX_ARTIFACT_BYTES, verify_artifact_bytes
from ..services.artifact_store import ArtifactStore
from ..services.audit import record_audit
from ..services.ecosystem import canonical_manifest_sha256
from ..services.execution import MAX_SECRET_LEASE_SECONDS, MIN_SECRET_LEASE_SECONDS

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


@router.get("/secret-grants", response_model=list[SecretGrantRead])
async def list_secret_grants(
    api_key: DeveloperApiKey = Depends(require_api_key_scopes("plugin:read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(SecretGrant)
        .where(SecretGrant.organization_id == api_key.organization_id)
        .order_by(SecretGrant.created_at.desc())
    )
    return list(rows.all())


@router.post("/secret-grants", response_model=SecretGrantRead, status_code=201)
async def request_secret_grant(
    payload: SecretGrantCreate,
    request: Request,
    api_key: DeveloperApiKey = Depends(require_api_key_scopes("plugin:execute")),
    db: AsyncSession = Depends(get_db),
):
    installation = await _installation_for_org(
        db,
        payload.installation_id,
        api_key.organization_id,
    )
    if installation.status != "approved" or "secret.read" not in set(installation.approved_scopes or []):
        raise HTTPException(
            status_code=409,
            detail="The plugin installation does not have the approved secret.read scope",
        )

    integration = await db.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.id == payload.integration_id,
            IntegrationConnection.organization_id == api_key.organization_id,
            IntegrationConnection.status == "active",
        )
    )
    if integration is None:
        raise HTTPException(status_code=404, detail="Active integration not found")
    if not integration.secret_ref:
        raise HTTPException(status_code=409, detail="Integration has no configured external secret reference")

    existing = await db.scalar(
        select(SecretGrant).where(
            SecretGrant.organization_id == api_key.organization_id,
            SecretGrant.installation_id == installation.id,
            SecretGrant.integration_id == integration.id,
            SecretGrant.status != "revoked",
        )
    )
    if existing:
        now = datetime.now(timezone.utc)
        if (
            existing.status == "approved"
            and (existing.expires_at is None or existing.expires_at <= now)
        ):
            existing.status = "revoked"
            existing.approved_scopes = []
            existing.approval_note = "Automatically expired before a new grant request."
            existing.approved_at = now
            await record_audit(
                db,
                action="developer.secret_grant.expired",
                resource_type="secret_grant",
                actor_user_id=api_key.created_by_user_id,
                organization_id=api_key.organization_id,
                resource_id=str(existing.id),
                detail={"installation_id": str(installation.id), "integration_id": str(integration.id)},
                request_id=getattr(request.state, "request_id", None),
            )
            await db.flush()
        else:
            return existing

    grant = SecretGrant(
        organization_id=api_key.organization_id,
        installation_id=installation.id,
        integration_id=integration.id,
        created_by_user_id=api_key.created_by_user_id,
        status="requested",
        approved_scopes=["secret.read"],
    )
    db.add(grant)
    await db.flush()
    await record_audit(
        db,
        action="developer.secret_grant.requested",
        resource_type="secret_grant",
        actor_user_id=api_key.created_by_user_id,
        organization_id=api_key.organization_id,
        resource_id=str(grant.id),
        detail={
            "installation_id": str(installation.id),
            "integration_id": str(integration.id),
            "scope": "secret.read",
        },
        request_id=getattr(request.state, "request_id", None),
    )
    await db.commit()
    await db.refresh(grant)
    return grant


@router.post("/secret-grants/{grant_id}/approve", response_model=SecretGrantRead)
async def approve_secret_grant(
    grant_id: UUID,
    payload: SecretGrantApproval,
    request: Request,
    user: User = Depends(require_roles("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    grant = await db.scalar(
        select(SecretGrant).where(
            SecretGrant.id == grant_id,
            SecretGrant.organization_id == membership.organization_id,
        )
    )
    if grant is None:
        raise HTTPException(status_code=404, detail="Secret grant not found")
    if grant.status != "requested":
        raise HTTPException(status_code=409, detail="Only requested secret grants can be reviewed")
    if payload.status == "approved" and not payload.note.strip():
        raise HTTPException(status_code=422, detail="An approval note is required")

    now = datetime.now(timezone.utc)
    expires_at = payload.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if payload.status == "approved":
        if expires_at is None:
            raise HTTPException(
                status_code=422,
                detail="An explicit secret lease expiration is required",
            )
        minimum_expiry = now + timedelta(seconds=MIN_SECRET_LEASE_SECONDS)
        maximum_expiry = now + timedelta(seconds=MAX_SECRET_LEASE_SECONDS)
        if not minimum_expiry <= expires_at <= maximum_expiry:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Secret lease expiration must be between "
                    f"{MIN_SECRET_LEASE_SECONDS} seconds and {MAX_SECRET_LEASE_SECONDS} seconds from now"
                ),
            )
    else:
        expires_at = None

    grant.status = payload.status
    grant.approved_scopes = ["secret.read"] if payload.status == "approved" else []
    grant.approval_note = payload.note.strip()
    grant.approved_by_user_id = user.id
    grant.approved_at = now
    grant.expires_at = expires_at
    await record_audit(
        db,
        action="developer.secret_grant.reviewed",
        resource_type="secret_grant",
        actor_user_id=user.id,
        organization_id=membership.organization_id,
        resource_id=str(grant.id),
        detail={"status": grant.status, "scope": "secret.read"},
        request_id=getattr(request.state, "request_id", None),
    )
    await db.commit()
    await db.refresh(grant)
    return grant





@router.get("/trust-roots", response_model=list[PluginTrustRootRead])
async def list_trust_roots(
    api_key: DeveloperApiKey = Depends(require_api_key_scopes("plugin:read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(
        select(PluginTrustRoot)
        .where(PluginTrustRoot.organization_id == api_key.organization_id)
        .order_by(PluginTrustRoot.created_at.desc())
    )
    return list(rows.all())


@router.post("/trust-roots", response_model=PluginTrustRootRead, status_code=201)
async def create_trust_root(
    payload: PluginTrustRootCreate,
    request: Request,
    user: User = Depends(require_roles("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    existing = await db.scalar(
        select(PluginTrustRoot).where(
            PluginTrustRoot.organization_id == membership.organization_id,
            PluginTrustRoot.key_id == payload.key_id,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="A trust root with this key_id already exists")

    try:
        from ..services.artifact_verification import decode_public_key

        decode_public_key(payload.public_key)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    root = PluginTrustRoot(
        organization_id=membership.organization_id,
        created_by_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(root)
    await db.flush()
    await record_audit(
        db,
        action="developer.plugin_trust_root.created",
        resource_type="plugin_trust_root",
        actor_user_id=user.id,
        organization_id=membership.organization_id,
        resource_id=str(root.id),
        detail={"key_id": root.key_id, "algorithm": root.algorithm},
        request_id=getattr(request.state, "request_id", None),
    )
    await db.commit()
    await db.refresh(root)
    return root


@router.post("/trust-roots/{trust_root_id}/revoke", response_model=PluginTrustRootRead)
async def revoke_trust_root(
    trust_root_id: UUID,
    request: Request,
    user: User = Depends(require_roles("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    root = await db.scalar(
        select(PluginTrustRoot).where(
            PluginTrustRoot.id == trust_root_id,
            PluginTrustRoot.organization_id == membership.organization_id,
        )
    )
    if root is None:
        raise HTTPException(status_code=404, detail="Trust root not found")
    if root.status != "active":
        raise HTTPException(status_code=409, detail="Trust root has already been revoked")

    root.status = "revoked"
    root.revoked_by_user_id = user.id
    root.revoked_at = datetime.now(timezone.utc)
    await record_audit(
        db,
        action="developer.plugin_trust_root.revoked",
        resource_type="plugin_trust_root",
        actor_user_id=user.id,
        organization_id=membership.organization_id,
        resource_id=str(root.id),
        detail={"key_id": root.key_id},
        request_id=getattr(request.state, "request_id", None),
    )
    await db.commit()
    await db.refresh(root)
    return root


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

    expected_manifest_sha256 = canonical_manifest_sha256(plugin.manifest or {})
    if payload.manifest_sha256.lower() != expected_manifest_sha256:
        raise HTTPException(
            status_code=422,
            detail="manifest_sha256 must match the plugin manifest currently registered for this release",
        )

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
        manifest_snapshot=plugin.manifest or {},
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




@router.post(
    "/plugin-releases/{release_id}/verify-artifact",
    response_model=PluginReleaseRead,
)
async def verify_release_artifact(
    release_id: UUID,
    payload: PluginArtifactVerification,
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
        raise HTTPException(
            status_code=409,
            detail="Artifact verification is only allowed before release review",
        )

    root = await db.scalar(
        select(PluginTrustRoot).where(
            PluginTrustRoot.id == payload.trust_root_id,
            PluginTrustRoot.organization_id == membership.organization_id,
        )
    )
    if root is None:
        raise HTTPException(status_code=404, detail="Trust root not found")
    if root.status != "active":
        raise HTTPException(status_code=409, detail="Trust root is revoked")
    if release.signer != root.key_id:
        raise HTTPException(
            status_code=422,
            detail="Release signer does not match the selected trust root",
        )

    try:
        artifact = base64.b64decode(payload.artifact_base64, validate=True)
        if len(artifact) > MAX_ARTIFACT_BYTES:
            raise ValueError(
                f"Artifact verification input cannot exceed {MAX_ARTIFACT_BYTES} bytes"
            )
        verify_artifact_bytes(
            artifact_bytes=artifact,
            expected_sha256=release.package_sha256,
            signature=release.signature,
            public_key=root.public_key,
        )
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    store = ArtifactStore(settings.artifact_root, max_bytes=MAX_ARTIFACT_BYTES)
    try:
        storage_key = store.put_verified(artifact, release.package_sha256)
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Verified artifact could not be durably staged",
        ) from exc

    release.artifact_verified_at = datetime.now(timezone.utc)
    release.artifact_verified_by_user_id = user.id
    release.verification_key_id = root.key_id
    release.verification_method = "ed25519-sha256"
    release.artifact_storage_key = storage_key
    release.artifact_size_bytes = len(artifact)
    release.artifact_staged_at = datetime.now(timezone.utc)
    await record_audit(
        db,
        action="developer.plugin_release.artifact_verified",
        resource_type="plugin_release",
        actor_user_id=user.id,
        organization_id=membership.organization_id,
        resource_id=str(release.id),
        detail={
            "version": release.version,
            "key_id": root.key_id,
            "method": release.verification_method,
            "storage_key": release.artifact_storage_key,
            "size_bytes": release.artifact_size_bytes,
        },
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
    if payload.status == "verified":
        if not release.artifact_verified_at or not release.verification_key_id:
            raise HTTPException(
                status_code=409,
                detail="Cryptographic artifact verification is required before release approval",
            )
        trust_root = await db.scalar(
            select(PluginTrustRoot).where(
                PluginTrustRoot.organization_id == membership.organization_id,
                PluginTrustRoot.key_id == release.verification_key_id,
                PluginTrustRoot.status == "active",
            )
        )
        if trust_root is None:
            raise HTTPException(
                status_code=409,
                detail="The release verification trust root is no longer active",
            )
        if not payload.note.strip():
            raise HTTPException(
                status_code=422,
                detail="A verification note is required when approving a plugin release",
            )

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
    release, _plugin = row
    if release.status != "verified" or not release.artifact_verified_at:
        raise HTTPException(
            status_code=409,
            detail="Only cryptographically verified plugin releases can be installed",
        )
    trust_root = await db.scalar(
        select(PluginTrustRoot).where(
            PluginTrustRoot.organization_id == api_key.organization_id,
            PluginTrustRoot.key_id == release.verification_key_id,
            PluginTrustRoot.status == "active",
        )
    )
    if trust_root is None:
        raise HTTPException(
            status_code=409,
            detail="The release verification trust root is no longer active",
        )

    manifest_snapshot = release.manifest_snapshot
    if not isinstance(manifest_snapshot, dict):
        raise HTTPException(
            status_code=409,
            detail="Plugin release does not contain a frozen manifest snapshot",
        )
    declared_capabilities = manifest_snapshot.get("capabilities", [])
    if not isinstance(declared_capabilities, list) or any(
        not isinstance(capability, str) for capability in declared_capabilities
    ):
        raise HTTPException(status_code=409, detail="Plugin release manifest has no valid capabilities declaration")
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
    if release is None or release.status != "verified" or not release.artifact_verified_at:
        raise HTTPException(
            status_code=409,
            detail="A cryptographically verified release is required before approval",
        )
    trust_root = await db.scalar(
        select(PluginTrustRoot).where(
            PluginTrustRoot.organization_id == membership.organization_id,
            PluginTrustRoot.key_id == release.verification_key_id,
            PluginTrustRoot.status == "active",
        )
    )
    if trust_root is None:
        raise HTTPException(
            status_code=409,
            detail="The release verification trust root is no longer active",
        )

    if payload.status == "approved" and not payload.note.strip():
        raise HTTPException(
            status_code=422,
            detail="An approval note is required when approving a plugin installation",
        )

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

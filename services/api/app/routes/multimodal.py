from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import get_current_user, get_membership
from ..db.session import get_db
from ..models import MultimodalAsset, User, WorkbenchProject
from ..schemas.multimodal import MultimodalAssetCreate, MultimodalAssetRead

router = APIRouter(prefix="/multimodal", tags=["multimodal-assets"])


async def _project_in_tenant(
    db: AsyncSession, project_id: UUID, organization_id: UUID
) -> WorkbenchProject:
    project = await db.scalar(
        select(WorkbenchProject).where(
            WorkbenchProject.id == project_id,
            WorkbenchProject.organization_id == organization_id,
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Workbench project not found")
    return project


@router.get(
    "/projects/{project_id}/assets",
    response_model=list[MultimodalAssetRead],
)
async def list_assets(
    project_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=10000),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    await _project_in_tenant(db, project_id, membership.organization_id)
    rows = await db.scalars(
        select(MultimodalAsset)
        .where(MultimodalAsset.project_id == project_id)
        .order_by(MultimodalAsset.created_at.desc(), MultimodalAsset.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/assets",
    response_model=MultimodalAssetRead,
    status_code=201,
)
async def create_asset(
    project_id: UUID,
    payload: MultimodalAssetCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    await _project_in_tenant(db, project_id, membership.organization_id)
    asset = MultimodalAsset(
        project_id=project_id,
        owner_id=user.id,
        name=payload.name,
        modality=payload.modality,
        source_reference=payload.source_reference,
        media_type=payload.media_type,
        sha256=payload.sha256.lower() if payload.sha256 else None,
        byte_size=payload.byte_size,
        duration_ms=payload.duration_ms,
        width=payload.width,
        height=payload.height,
        metadata_json=payload.metadata,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


@router.get("/assets/{asset_id}", response_model=MultimodalAssetRead)
async def get_asset(
    asset_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    asset = await db.scalar(
        select(MultimodalAsset)
        .join(WorkbenchProject, MultimodalAsset.project_id == WorkbenchProject.id)
        .where(
            MultimodalAsset.id == asset_id,
            WorkbenchProject.organization_id == membership.organization_id,
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Multimodal asset not found")
    return asset

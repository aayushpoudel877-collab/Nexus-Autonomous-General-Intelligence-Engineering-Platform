from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import get_current_user, get_membership
from ..db.session import get_db
from ..models import BenchmarkComparison, RegisteredModel, User, WorkbenchProject
from ..schemas.benchmarks import BenchmarkComparisonCreate, BenchmarkComparisonRead
from ..services.benchmarks import compare_metrics

router = APIRouter(prefix="/benchmarks", tags=["continuous-improvement"])


async def _project_in_tenant(db: AsyncSession, project_id: UUID, organization_id: UUID):
    project = await db.scalar(select(WorkbenchProject).where(
        WorkbenchProject.id == project_id,
        WorkbenchProject.organization_id == organization_id,
    ))
    if project is None:
        raise HTTPException(status_code=404, detail="Workbench project not found")
    return project


@router.get("/projects/{project_id}/comparisons", response_model=list[BenchmarkComparisonRead])
async def list_comparisons(
    project_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=10000),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    await _project_in_tenant(db, project_id, membership.organization_id)
    rows = await db.scalars(
        select(BenchmarkComparison)
        .where(BenchmarkComparison.project_id == project_id)
        .order_by(BenchmarkComparison.created_at.desc(), BenchmarkComparison.id.desc())
        .offset(offset).limit(limit)
    )
    return list(rows.all())


@router.post("/projects/{project_id}/comparisons", response_model=BenchmarkComparisonRead, status_code=201)
async def create_comparison(
    project_id: UUID,
    payload: BenchmarkComparisonCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    await _project_in_tenant(db, project_id, membership.organization_id)
    rows = await db.scalars(select(RegisteredModel).where(
        RegisteredModel.id.in_([payload.baseline_model_id, payload.candidate_model_id]),
        RegisteredModel.project_id == project_id,
        RegisteredModel.status != "archived",
    ))
    found = {model.id for model in rows.all()}
    if found != {payload.baseline_model_id, payload.candidate_model_id}:
        raise HTTPException(status_code=422, detail="Baseline and candidate models must both be non-archived models in this project")
    criteria = {name: item.model_dump() for name, item in payload.criteria.items()}
    passed, deltas, issues = compare_metrics(payload.baseline_metrics, payload.candidate_metrics, criteria)
    summary = payload.summary.strip()
    if issues:
        summary = (summary + "\n" + "; ".join(issues)).strip()
    comparison = BenchmarkComparison(
        project_id=project_id, owner_id=user.id,
        baseline_model_id=payload.baseline_model_id, candidate_model_id=payload.candidate_model_id,
        baseline_metrics=payload.baseline_metrics, candidate_metrics=payload.candidate_metrics,
        criteria=criteria, deltas=deltas,
        status="passed" if passed else "needs_improvement", summary=summary,
    )
    db.add(comparison)
    await db.commit()
    await db.refresh(comparison)
    return comparison

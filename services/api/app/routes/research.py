from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.dependencies import get_current_user, get_membership
from ..db.session import get_db
from ..models import (
    ResearchPlan,
    ResearchTask,
    User,
    WorkbenchProject,
)
from ..schemas.research import (
    ResearchPlanCreate,
    ResearchPlanRead,
    ResearchTaskCreate,
    ResearchTaskRead,
    ResearchTaskUpdate,
)
from ..services.research import (
    dependencies_succeeded,
    ensure_task_transition,
    validate_dependencies,
)

router = APIRouter(prefix="/research", tags=["autonomous-research"])


async def _owned_plan(
    db: AsyncSession, plan_id: UUID, organization_id: UUID
) -> ResearchPlan:
    plan = await db.scalar(
        select(ResearchPlan).where(
            ResearchPlan.id == plan_id,
            ResearchPlan.organization_id == organization_id,
        )
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Research plan not found")
    return plan


@router.get("/plans", response_model=list[ResearchPlanRead])
async def list_plans(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    membership = await get_membership(user, db)
    rows = await db.scalars(
        select(ResearchPlan)
        .options(selectinload(ResearchPlan.tasks))
        .where(ResearchPlan.organization_id == membership.organization_id)
        .order_by(ResearchPlan.updated_at.desc())
        .limit(100)
    )
    return list(rows.all())


@router.post("/plans", response_model=ResearchPlanRead, status_code=201)
async def create_plan(
    payload: ResearchPlanCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    if payload.workbench_project_id:
        project = await db.scalar(
            select(WorkbenchProject).where(
                WorkbenchProject.id == payload.workbench_project_id,
                WorkbenchProject.organization_id == membership.organization_id,
            )
        )
        if not project:
            raise HTTPException(status_code=404, detail="Workbench project not found")
    plan = ResearchPlan(
        organization_id=membership.organization_id,
        owner_id=user.id,
        **payload.model_dump(),
    )
    db.add(plan)
    await db.commit()
    plan = await db.scalar(
        select(ResearchPlan)
        .options(selectinload(ResearchPlan.tasks))
        .where(ResearchPlan.id == plan.id)
    )
    return plan


@router.get("/plans/{plan_id}", response_model=ResearchPlanRead)
async def get_plan(
    plan_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    plan = await db.scalar(
        select(ResearchPlan)
        .options(selectinload(ResearchPlan.tasks))
        .where(
            ResearchPlan.id == plan_id,
            ResearchPlan.organization_id == membership.organization_id,
        )
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Research plan not found")
    return plan


@router.post(
    "/plans/{plan_id}/tasks", response_model=ResearchTaskRead, status_code=201
)
async def create_task(
    plan_id: UUID,
    payload: ResearchTaskCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    plan = await _owned_plan(db, plan_id, membership.organization_id)
    requested_ids = [str(value) for value in payload.depends_on]
    if requested_ids:
        dependencies = await db.scalars(
            select(ResearchTask).where(
                ResearchTask.plan_id == plan.id,
                ResearchTask.id.in_(payload.depends_on),
            )
        )
        available = {str(task.id) for task in dependencies.all()}
    else:
        available = set()
    try:
        validate_dependencies(requested_ids, available)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    task = ResearchTask(
        plan_id=plan.id,
        title=payload.title,
        description=payload.description,
        task_type=payload.task_type,
        depends_on=requested_ids,
        status="planned" if requested_ids else "ready",
    )
    plan.status = "active"
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.patch("/tasks/{task_id}", response_model=ResearchTaskRead)
async def update_task(
    task_id: UUID,
    payload: ResearchTaskUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    task = await db.scalar(
        select(ResearchTask)
        .join(ResearchPlan, ResearchTask.plan_id == ResearchPlan.id)
        .where(
            ResearchTask.id == task_id,
            ResearchPlan.organization_id == membership.organization_id,
        )
    )
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")

    updates = payload.model_dump(exclude_unset=True)
    requested_status = updates.get("status")
    if requested_status:
        try:
            ensure_task_transition(task.status, requested_status)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if requested_status == "running" and task.depends_on:
            dependency_ids = [UUID(value) for value in task.depends_on]
            dependencies = await db.scalars(
                select(ResearchTask).where(
                    ResearchTask.plan_id == task.plan_id,
                    ResearchTask.id.in_(dependency_ids),
                )
            )
            statuses = [item.status for item in dependencies.all()]
            if not dependencies_succeeded(statuses) or len(statuses) != len(dependency_ids):
                raise HTTPException(
                    status_code=409,
                    detail="All task dependencies must succeed before this task can run",
                )

    for key, value in updates.items():
        setattr(task, key, value)
    await db.commit()
    await db.refresh(task)
    return task

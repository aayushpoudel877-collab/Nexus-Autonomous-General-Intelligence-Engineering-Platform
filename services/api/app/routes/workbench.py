from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import get_current_user, get_membership
from ..db.session import get_db
from ..models import (
    User,
    WorkbenchDataset,
    WorkbenchExperiment,
    WorkbenchProject,
)
from ..services.workbench import ensure_status_transition
from ..schemas.workbench import (
    DatasetCreate,
    DatasetRead,
    ExperimentCreate,
    ExperimentRead,
    ExperimentUpdate,
    ProjectCreate,
    ProjectRead,
)

router = APIRouter(prefix="/workbench", tags=["ai-engineering-workbench"])


async def _owned_project(
    db: AsyncSession, project_id: UUID, organization_id: UUID
) -> WorkbenchProject:
    project = await db.scalar(
        select(WorkbenchProject).where(
            WorkbenchProject.id == project_id,
            WorkbenchProject.organization_id == organization_id,
        )
    )
    if not project:
        raise HTTPException(status_code=404, detail="Workbench project not found")
    return project


@router.get("/projects", response_model=list[ProjectRead])
async def list_projects(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    membership = await get_membership(user, db)
    projects = await db.scalars(
        select(WorkbenchProject)
        .where(WorkbenchProject.organization_id == membership.organization_id)
        .order_by(WorkbenchProject.created_at.desc())
        .limit(100)
    )
    return list(projects.all())


@router.post("/projects", response_model=ProjectRead, status_code=201)
async def create_project(
    payload: ProjectCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    project = WorkbenchProject(
        organization_id=membership.organization_id,
        owner_id=user.id,
        **payload.model_dump(),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/projects/{project_id}/datasets", response_model=list[DatasetRead])
async def list_datasets(
    project_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    await _owned_project(db, project_id, membership.organization_id)
    rows = await db.scalars(
        select(WorkbenchDataset)
        .where(WorkbenchDataset.project_id == project_id)
        .order_by(WorkbenchDataset.created_at.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/datasets", response_model=DatasetRead, status_code=201
)
async def create_dataset(
    project_id: UUID,
    payload: DatasetCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    await _owned_project(db, project_id, membership.organization_id)
    dataset = WorkbenchDataset(project_id=project_id, **payload.model_dump())
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


@router.get(
    "/projects/{project_id}/experiments", response_model=list[ExperimentRead]
)
async def list_experiments(
    project_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    await _owned_project(db, project_id, membership.organization_id)
    rows = await db.scalars(
        select(WorkbenchExperiment)
        .where(WorkbenchExperiment.project_id == project_id)
        .order_by(WorkbenchExperiment.created_at.desc())
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/experiments",
    response_model=ExperimentRead,
    status_code=201,
)
async def create_experiment(
    project_id: UUID,
    payload: ExperimentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    await _owned_project(db, project_id, membership.organization_id)
    values = payload.model_dump()
    dataset_id = values.pop("dataset_id")
    if dataset_id:
        dataset = await db.scalar(
            select(WorkbenchDataset).where(
                WorkbenchDataset.id == dataset_id,
                WorkbenchDataset.project_id == project_id,
            )
        )
        if not dataset:
            raise HTTPException(
                status_code=422, detail="Dataset must belong to the selected project"
            )
    experiment = WorkbenchExperiment(
        project_id=project_id, dataset_id=dataset_id, **values
    )
    db.add(experiment)
    await db.commit()
    await db.refresh(experiment)
    return experiment


@router.patch("/experiments/{experiment_id}", response_model=ExperimentRead)
async def update_experiment(
    experiment_id: UUID,
    payload: ExperimentUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    experiment = await db.scalar(
        select(WorkbenchExperiment)
        .join(WorkbenchProject, WorkbenchExperiment.project_id == WorkbenchProject.id)
        .where(
            WorkbenchExperiment.id == experiment_id,
            WorkbenchProject.organization_id == membership.organization_id,
        )
    )
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("status") is not None:
        try:
            ensure_status_transition(experiment.status, updates["status"])
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    for key, value in updates.items():
        setattr(experiment, key, value)
    await db.commit()
    await db.refresh(experiment)
    return experiment

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.dependencies import get_current_user, get_membership
from ..db.session import get_db
from ..models import (
    MLTrainingRun,
    ModelEvaluation,
    RegisteredModel,
    User,
    WorkbenchDataset,
    WorkbenchExperiment,
    WorkbenchProject,
)
from ..schemas.ml_lifecycle import (
    ModelEvaluationCreate,
    ModelEvaluationRead,
    ModelEvaluationUpdate,
    RegisteredModelCreate,
    RegisteredModelRead,
    RegisteredModelUpdate,
    TrainingRunCreate,
    TrainingRunRead,
    TrainingRunUpdate,
)
from ..services.ml_lifecycle import (
    ensure_evaluation_transition,
    ensure_model_transition,
    ensure_run_transition,
    utc_now,
)

router = APIRouter(prefix="/ml", tags=["ml-lifecycle"])


async def _project(
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


async def _model_in_tenant(
    db: AsyncSession, model_id: UUID, organization_id: UUID
) -> RegisteredModel:
    model = await db.scalar(
        select(RegisteredModel)
        .join(WorkbenchProject, RegisteredModel.project_id == WorkbenchProject.id)
        .where(
            RegisteredModel.id == model_id,
            WorkbenchProject.organization_id == organization_id,
        )
    )
    if not model:
        raise HTTPException(status_code=404, detail="Registered model not found")
    return model


@router.get(
    "/projects/{project_id}/training-runs", response_model=list[TrainingRunRead]
)
async def list_training_runs(
    project_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    await _project(db, project_id, membership.organization_id)
    rows = await db.scalars(
        select(MLTrainingRun)
        .where(MLTrainingRun.project_id == project_id)
        .order_by(MLTrainingRun.created_at.desc())
        .limit(100)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/training-runs",
    response_model=TrainingRunRead,
    status_code=201,
)
async def create_training_run(
    project_id: UUID,
    payload: TrainingRunCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    await _project(db, project_id, membership.organization_id)
    if payload.dataset_id:
        dataset = await db.scalar(
            select(WorkbenchDataset)
            .join(WorkbenchProject, WorkbenchDataset.project_id == WorkbenchProject.id)
            .where(
                WorkbenchDataset.id == payload.dataset_id,
                WorkbenchDataset.project_id == project_id,
                WorkbenchProject.organization_id == membership.organization_id,
            )
        )
        if not dataset:
            raise HTTPException(status_code=422, detail="Dataset must belong to this project")
    run = MLTrainingRun(
        project_id=project_id,
        owner_id=user.id,
        **payload.model_dump(),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


@router.patch("/training-runs/{run_id}", response_model=TrainingRunRead)
async def update_training_run(
    run_id: UUID,
    payload: TrainingRunUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    run = await db.scalar(
        select(MLTrainingRun)
        .join(WorkbenchProject, MLTrainingRun.project_id == WorkbenchProject.id)
        .where(
            MLTrainingRun.id == run_id,
            WorkbenchProject.organization_id == membership.organization_id,
        )
    )
    if not run:
        raise HTTPException(status_code=404, detail="Training run not found")
    updates = payload.model_dump(exclude_unset=True)
    requested_status = updates.get("status")
    if requested_status is not None:
        try:
            ensure_run_transition(run.status, requested_status)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        now = utc_now()
        if requested_status == "running" and run.started_at is None:
            run.started_at = now
        if requested_status in {"succeeded", "failed", "cancelled"}:
            run.finished_at = now
    for key, value in updates.items():
        setattr(run, key, value)
    await db.commit()
    await db.refresh(run)
    return run


@router.get("/projects/{project_id}/models", response_model=list[RegisteredModelRead])
async def list_models(
    project_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    await _project(db, project_id, membership.organization_id)
    rows = await db.scalars(
        select(RegisteredModel)
        .where(RegisteredModel.project_id == project_id)
        .order_by(RegisteredModel.created_at.desc())
        .limit(100)
    )
    return list(rows.all())


@router.post(
    "/projects/{project_id}/models", response_model=RegisteredModelRead, status_code=201
)
async def register_model(
    project_id: UUID,
    payload: RegisteredModelCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    await _project(db, project_id, membership.organization_id)
    values = payload.model_dump()
    run_id = values.pop("source_training_run_id")
    experiment_id = values.pop("source_experiment_id")
    if run_id:
        source = await db.scalar(
            select(MLTrainingRun)
            .join(WorkbenchProject, MLTrainingRun.project_id == WorkbenchProject.id)
            .where(
                MLTrainingRun.id == run_id,
                MLTrainingRun.project_id == project_id,
                MLTrainingRun.status == "succeeded",
                WorkbenchProject.organization_id == membership.organization_id,
            )
        )
        if not source:
            raise HTTPException(
                status_code=422,
                detail="Model source training run must have succeeded in this project",
            )
    if experiment_id:
        source = await db.scalar(
            select(WorkbenchExperiment)
            .join(WorkbenchProject, WorkbenchExperiment.project_id == WorkbenchProject.id)
            .where(
                WorkbenchExperiment.id == experiment_id,
                WorkbenchExperiment.project_id == project_id,
                WorkbenchExperiment.status == "succeeded",
                WorkbenchProject.organization_id == membership.organization_id,
            )
        )
        if not source:
            raise HTTPException(
                status_code=422,
                detail="Model source experiment must have succeeded in this project",
            )
    model = RegisteredModel(
        project_id=project_id,
        owner_id=user.id,
        source_training_run_id=run_id,
        source_experiment_id=experiment_id,
        **values,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


@router.patch("/models/{model_id}", response_model=RegisteredModelRead)
async def update_model(
    model_id: UUID,
    payload: RegisteredModelUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    model = await _model_in_tenant(db, model_id, membership.organization_id)
    updates = payload.model_dump(exclude_unset=True)
    requested_status = updates.get("status")
    if requested_status is not None:
        try:
            ensure_model_transition(model.status, requested_status)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if requested_status in {"validated", "approved"}:
            passed = await db.scalar(
                select(ModelEvaluation.id).where(
                    ModelEvaluation.model_id == model.id,
                    ModelEvaluation.status == "passed",
                ).limit(1)
            )
            if not passed:
                raise HTTPException(
                    status_code=409,
                    detail="At least one passed evaluation is required before validation or approval",
                )
        if requested_status == "approved" and not (updates.get("approval_note") or model.approval_note):
            raise HTTPException(
                status_code=422,
                detail="An approval note is required for human review traceability",
            )
    for key, value in updates.items():
        setattr(model, key, value)
    await db.commit()
    await db.refresh(model)
    return model


@router.get("/models/{model_id}/evaluations", response_model=list[ModelEvaluationRead])
async def list_evaluations(
    model_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    model = await _model_in_tenant(db, model_id, membership.organization_id)
    rows = await db.scalars(
        select(ModelEvaluation)
        .where(ModelEvaluation.model_id == model.id)
        .order_by(ModelEvaluation.created_at.desc())
        .limit(100)
    )
    return list(rows.all())


@router.post(
    "/models/{model_id}/evaluations",
    response_model=ModelEvaluationRead,
    status_code=201,
)
async def create_evaluation(
    model_id: UUID,
    payload: ModelEvaluationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    model = await _model_in_tenant(db, model_id, membership.organization_id)
    evaluation = ModelEvaluation(model_id=model.id, **payload.model_dump())
    db.add(evaluation)
    await db.commit()
    await db.refresh(evaluation)
    return evaluation


@router.patch("/evaluations/{evaluation_id}", response_model=ModelEvaluationRead)
async def update_evaluation(
    evaluation_id: UUID,
    payload: ModelEvaluationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    evaluation = await db.scalar(
        select(ModelEvaluation)
        .join(RegisteredModel, ModelEvaluation.model_id == RegisteredModel.id)
        .join(WorkbenchProject, RegisteredModel.project_id == WorkbenchProject.id)
        .where(
            ModelEvaluation.id == evaluation_id,
            WorkbenchProject.organization_id == membership.organization_id,
        )
    )
    if not evaluation:
        raise HTTPException(status_code=404, detail="Model evaluation not found")
    updates = payload.model_dump(exclude_unset=True)
    requested_status = updates.get("status")
    if requested_status is not None:
        try:
            ensure_evaluation_transition(evaluation.status, requested_status)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if requested_status in {"passed", "failed", "cancelled"}:
            evaluation.finished_at = utc_now()
    for key, value in updates.items():
        setattr(evaluation, key, value)
    await db.commit()
    await db.refresh(evaluation)
    return evaluation

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.dependencies import get_current_user, get_membership, require_roles
from ..db.session import get_db
from ..models import ResearchPlan, User, WorkbenchProject
from ..models.workflow import WorkflowApproval, WorkflowDefinition, WorkflowNode, WorkflowNodeRun, WorkflowRun
from ..schemas.workflow import WorkflowApprovalDecision, WorkflowCreate, WorkflowRead, WorkflowRunCreate, WorkflowRunRead
from ..services.audit import record_audit
from services.orchestrator.engine import tick_run
from ..services.workflow import build_workflow_policy_snapshot, ensure_node_run_transition, ensure_run_transition, validate_workflow_graph

router = APIRouter(prefix="/workflows", tags=["durable-workflows"])
LEASE_SECONDS = 120


async def _workflow(db: AsyncSession, workflow_id: UUID, organization_id: UUID) -> WorkflowDefinition:
    workflow = await db.scalar(
        select(WorkflowDefinition)
        .options(selectinload(WorkflowDefinition.nodes))
        .where(WorkflowDefinition.id == workflow_id, WorkflowDefinition.organization_id == organization_id)
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


async def _run(db: AsyncSession, run_id: UUID, organization_id: UUID) -> WorkflowRun:
    run = await db.scalar(
        select(WorkflowRun)
        .options(
            selectinload(WorkflowRun.node_runs).selectinload(WorkflowNodeRun.approvals),
            selectinload(WorkflowRun.approvals),
        )
        .where(WorkflowRun.id == run_id, WorkflowRun.organization_id == organization_id)
    )
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return run


@router.get("", response_model=list[WorkflowRead])
async def list_workflows(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    membership = await get_membership(user, db)
    rows = await db.scalars(
        select(WorkflowDefinition)
        .options(selectinload(WorkflowDefinition.nodes))
        .where(WorkflowDefinition.organization_id == membership.organization_id)
        .order_by(WorkflowDefinition.updated_at.desc())
        .limit(100)
    )
    return list(rows.all())


@router.post("", response_model=WorkflowRead, status_code=201)
async def create_workflow(
    payload: WorkflowCreate,
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
    if payload.research_plan_id:
        plan = await db.scalar(
            select(ResearchPlan).where(
                ResearchPlan.id == payload.research_plan_id,
                ResearchPlan.organization_id == membership.organization_id,
            )
        )
        if not plan:
            raise HTTPException(status_code=404, detail="Research plan not found")
    try:
        validate_workflow_graph([node.model_dump() for node in payload.nodes])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    workflow = WorkflowDefinition(
        organization_id=membership.organization_id,
        owner_id=user.id,
        workbench_project_id=payload.workbench_project_id,
        research_plan_id=payload.research_plan_id,
        name=payload.name,
        description=payload.description,
        status="active",
    )
    workflow.nodes = [WorkflowNode(**node.model_dump()) for node in payload.nodes]
    db.add(workflow)
    await record_audit(
        db,
        action="workflow.created",
        resource_type="workflow",
        actor_user_id=user.id,
        organization_id=membership.organization_id,
        resource_id=str(workflow.id),
        detail={"nodes": len(payload.nodes), "version": workflow.version},
    )
    await db.commit()
    return await _workflow(db, workflow.id, membership.organization_id)


@router.get("/{workflow_id}", response_model=WorkflowRead)
async def get_workflow(
    workflow_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    return await _workflow(db, workflow_id, membership.organization_id)


@router.post("/{workflow_id}/runs", response_model=WorkflowRunRead, status_code=201)
async def start_workflow(
    workflow_id: UUID,
    payload: WorkflowRunCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    workflow = await _workflow(db, workflow_id, membership.organization_id)
    if workflow.status != "active":
        raise HTTPException(status_code=409, detail="Only active workflows can be started")
    run = WorkflowRun(
        workflow_id=workflow.id,
        organization_id=membership.organization_id,
        created_by=user.id,
        status="queued",
        input_json=payload.input_json,
        context_json={"workflow_version": workflow.version},
        policy_snapshot=build_workflow_policy_snapshot(),
        started_at=None,
    )
    run.node_runs = [
        WorkflowNodeRun(node_id=node.id, status="pending", input_json=dict(payload.input_json))
        for node in workflow.nodes
    ]
    db.add(run)
    await record_audit(
        db,
        action="workflow.run.queued",
        resource_type="workflow_run",
        actor_user_id=user.id,
        organization_id=membership.organization_id,
        resource_id=str(run.id),
        detail={"workflow_id": str(workflow.id), "version": workflow.version},
    )
    await db.commit()
    return await _run(db, run.id, membership.organization_id)


@router.get("/{workflow_id}/runs", response_model=list[WorkflowRunRead])
async def list_workflow_runs(
    workflow_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    await _workflow(db, workflow_id, membership.organization_id)
    rows = await db.scalars(
        select(WorkflowRun)
        .options(
            selectinload(WorkflowRun.node_runs).selectinload(WorkflowNodeRun.approvals),
            selectinload(WorkflowRun.approvals),
        )
        .where(
            WorkflowRun.workflow_id == workflow_id,
            WorkflowRun.organization_id == membership.organization_id,
        )
        .order_by(WorkflowRun.created_at.desc())
        .limit(50)
    )
    return list(rows.all())


@router.post("/{workflow_id}/runs/{run_id}/tick", response_model=WorkflowRunRead)
async def tick_workflow(
    workflow_id: UUID,
    run_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    run = await _run(db, run_id, membership.organization_id)
    if run.workflow_id != workflow_id:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    try:
        await tick_run(
            db,
            run,
            organization_id=membership.organization_id,
            actor_user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()
    return await _run(db, run.id, membership.organization_id)


@router.post("/{workflow_id}/runs/{run_id}/cancel", response_model=WorkflowRunRead)
async def cancel_workflow(
    workflow_id: UUID,
    run_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    run = await _run(db, run_id, membership.organization_id)
    if run.workflow_id != workflow_id:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    try:
        ensure_run_transition(run.status, "cancelled")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    run.status = "cancelled"
    run.finished_at = datetime.now(timezone.utc)
    for node_run in run.node_runs:
        if node_run.status not in {"succeeded", "failed", "cancelled"}:
            node_run.status = "cancelled"
            node_run.lease_expires_at = None
    await record_audit(
        db,
        action="workflow.run.cancelled",
        resource_type="workflow_run",
        actor_user_id=user.id,
        organization_id=membership.organization_id,
        resource_id=str(run.id),
    )
    await db.commit()
    return await _run(db, run.id, membership.organization_id)


@router.post("/{workflow_id}/runs/{run_id}/approvals/{approval_id}", response_model=WorkflowRunRead)
async def decide_workflow_approval(
    workflow_id: UUID,
    run_id: UUID,
    approval_id: UUID,
    payload: WorkflowApprovalDecision,
    user: User = Depends(require_roles("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    membership = await get_membership(user, db)
    run = await _run(db, run_id, membership.organization_id)
    if run.workflow_id != workflow_id:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    approval = next((item for item in run.approvals if item.id == approval_id), None)
    if approval is None or approval.status != "pending":
        raise HTTPException(status_code=404, detail="Pending workflow approval not found")
    node_run = next((item for item in run.node_runs if item.id == approval.node_run_id), None)
    if node_run is None:
        raise HTTPException(status_code=409, detail="Workflow approval node run is missing")
    approval.status = payload.status
    approval.decision_note = payload.note
    approval.decided_by = user.id
    approval.decided_at = datetime.now(timezone.utc)
    if payload.status == "approved":
        ensure_node_run_transition(node_run.status, "running")
        node_run.status = "running"
        ensure_node_run_transition(node_run.status, "succeeded")
        node_run.status = "succeeded"
        node_run.attempt += 1
        node_run.started_at = node_run.started_at or approval.decided_at
        node_run.finished_at = approval.decided_at
        node_run.lease_expires_at = None
        node_run.output_json = {"decision": "approved", "note": payload.note}
        run.status = "running"
        run.context_json = {**run.context_json, "last_approval": str(approval.id)}
    else:
        ensure_node_run_transition(node_run.status, "failed")
        node_run.status = "failed"
        node_run.error_message = payload.note or "Human approval rejected"
        node_run.finished_at = approval.decided_at
        node_run.lease_expires_at = None
        run.status = "failed"
        run.finished_at = approval.decided_at
    await record_audit(
        db,
        action="workflow.approval.decided",
        resource_type="workflow_approval",
        actor_user_id=user.id,
        organization_id=membership.organization_id,
        resource_id=str(approval.id),
        detail={"status": payload.status},
    )
    await db.commit()
    return await _run(db, run.id, membership.organization_id)

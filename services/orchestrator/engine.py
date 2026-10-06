"""Database-backed workflow tick engine shared by API and worker processes."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.api.app.models import ExecutionRequest, ResearchPlan, ResearchTask
from services.api.app.models.workflow import WorkflowApproval, WorkflowDefinition, WorkflowNode, WorkflowNodeRun, WorkflowRun
from services.api.app.services.audit import record_audit
from services.api.app.services.workflow import (
    classify_run_after_tick,
    ensure_node_run_transition,
    ensure_run_transition,
    ready_node_keys,
    validate_workflow_graph,
)

DEFAULT_LEASE_SECONDS = 120


async def load_run(db: AsyncSession, run_id: UUID) -> WorkflowRun | None:
    return await db.scalar(
        select(WorkflowRun)
        .options(
            selectinload(WorkflowRun.workflow).selectinload(WorkflowDefinition.nodes),
            selectinload(WorkflowRun.node_runs).selectinload(WorkflowNodeRun.approvals),
            selectinload(WorkflowRun.approvals),
        )
        .where(WorkflowRun.id == run_id)
    )


async def _sync_external_node(
    db: AsyncSession,
    node: WorkflowNode,
    node_run: WorkflowNodeRun,
    organization_id: UUID,
    now: datetime,
    lease_seconds: int,
) -> None:
    if node.node_type == "research_task":
        try:
            task_id = UUID(str(node.config.get("research_task_id")))
        except (ValueError, TypeError):
            node_run.status = "failed"
            node_run.error_message = "Invalid research_task_id"
            node_run.finished_at = now
            node_run.lease_expires_at = None
            return
        task = await db.scalar(
            select(ResearchTask)
            .join(ResearchPlan, ResearchTask.plan_id == ResearchPlan.id)
            .where(ResearchTask.id == task_id, ResearchPlan.organization_id == organization_id)
        )
        if not task:
            node_run.status = "failed"
            node_run.error_message = "Referenced research task not found"
            node_run.finished_at = now
            node_run.lease_expires_at = None
            return
        node_run.output_json = {"research_task_id": str(task.id), "external_status": task.status}
        if task.status == "succeeded":
            ensure_node_run_transition(node_run.status, "succeeded")
            node_run.status = "succeeded"
            node_run.finished_at = now
            node_run.lease_expires_at = None
        elif task.status in {"failed", "cancelled"}:
            ensure_node_run_transition(node_run.status, "failed")
            node_run.status = "failed"
            node_run.error_message = task.output_summary or f"Research task ended with status {task.status}"
            node_run.finished_at = now
            node_run.lease_expires_at = None
        else:
            node_run.lease_expires_at = now + timedelta(seconds=lease_seconds)
        return

    try:
        execution_id = UUID(str(node.config.get("execution_request_id")))
    except (ValueError, TypeError):
        node_run.status = "failed"
        node_run.error_message = "Invalid execution_request_id"
        node_run.finished_at = now
        node_run.lease_expires_at = None
        return
    execution = await db.scalar(
        select(ExecutionRequest).where(
            ExecutionRequest.id == execution_id,
            ExecutionRequest.organization_id == organization_id,
        )
    )
    if not execution:
        node_run.status = "failed"
        node_run.error_message = "Referenced execution request not found"
        node_run.finished_at = now
        node_run.lease_expires_at = None
        return
    node_run.output_json = {"execution_request_id": str(execution.id), "external_status": execution.status}
    if execution.status == "succeeded":
        ensure_node_run_transition(node_run.status, "succeeded")
        node_run.status = "succeeded"
        node_run.finished_at = now
        node_run.lease_expires_at = None
    elif execution.status in {"failed", "cancelled"}:
        ensure_node_run_transition(node_run.status, "failed")
        node_run.status = "failed"
        node_run.error_message = execution.failure_reason or f"Execution ended with status {execution.status}"
        node_run.finished_at = now
        node_run.lease_expires_at = None
    else:
        node_run.lease_expires_at = now + timedelta(seconds=lease_seconds)


async def tick_run(
    db: AsyncSession,
    run: WorkflowRun,
    *,
    organization_id: UUID,
    worker_id: str | None = None,
    actor_user_id: UUID | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> WorkflowRun:
    now = datetime.now(timezone.utc)
    if run.status in {"cancelled", "succeeded", "failed"}:
        return run
    if worker_id is not None:
        if run.worker_id not in {None, worker_id}:
            raise ValueError("Workflow run is owned by another worker lease")
        run.worker_id = worker_id
        run.heartbeat_at = now
        run.lease_expires_at = now + timedelta(seconds=lease_seconds)
    if run.status == "queued":
        ensure_run_transition(run.status, "running")
        run.status = "running"
        run.started_at = run.started_at or now

    workflow = run.workflow
    node_list = list(workflow.nodes)
    validate_workflow_graph(
        [{"node_key": n.node_key, "node_type": n.node_type, "depends_on": n.depends_on} for n in node_list]
    )
    node_by_key = {node.node_key: node for node in node_list}
    node_runs_by_id = {item.node_id: item for item in run.node_runs}
    statuses = {node.node_key: node_runs_by_id[node.id].status for node in node_list}
    progress = True
    ready_seen: list[str] = []

    while progress:
        progress = False
        ready_keys = ready_node_keys(
            [{"node_key": node.node_key, "depends_on": node.depends_on} for node in node_list], statuses
        )
        if not ready_keys:
            break
        for key in ready_keys:
            node = node_by_key[key]
            node_run = node_runs_by_id[node.id]
            ready_seen.append(key)
            if node.node_type == "approval":
                if not any(approval.status == "pending" for approval in node_run.approvals):
                    db.add(
                        WorkflowApproval(
                            run_id=run.id,
                            node_run_id=node_run.id,
                            prompt=str(node.config.get("prompt", f"Approve workflow node '{node.title}'")),
                        )
                    )
                ensure_node_run_transition(node_run.status, "ready")
                node_run.status = "ready"
                statuses[key] = "ready"
                progress = True
                continue

            ensure_node_run_transition(node_run.status, "ready")
            node_run.status = "ready"
            ensure_node_run_transition(node_run.status, "running")
            node_run.status = "running"
            node_run.attempt += 1
            node_run.started_at = node_run.started_at or now
            node_run.lease_expires_at = now + timedelta(seconds=lease_seconds)
            if node.node_type == "checkpoint":
                node_run.output_json = {"checkpoint": node.node_key, "workflow_version": run.context_json.get("workflow_version", 1)}
                ensure_node_run_transition(node_run.status, "succeeded")
                node_run.status = "succeeded"
                node_run.finished_at = now
                node_run.lease_expires_at = None
            else:
                await _sync_external_node(
                    db, node, node_run, organization_id, now, lease_seconds
                )
            statuses[key] = node_run.status
            progress = True

    approval_pending = any(approval.status == "pending" for approval in run.approvals) or any(
        node.node_type == "approval" and node_runs_by_id[node.id].status == "ready" for node in node_list
    )
    new_status = classify_run_after_tick(statuses, approval_pending)
    if new_status != run.status:
        ensure_run_transition(run.status, new_status)
        run.status = new_status
        if new_status == "paused":
            run.context_json = {**run.context_json, "pause_reason": "human_approval_required"}
        if new_status in {"succeeded", "failed"}:
            run.finished_at = now
            run.worker_id = None
            run.lease_expires_at = None
    elif worker_id is not None and run.status == "running":
        run.worker_id = worker_id
        run.heartbeat_at = now
        run.lease_expires_at = now + timedelta(seconds=lease_seconds)

    if actor_user_id is not None:
        await record_audit(
            db,
            action="workflow.run.ticked",
            resource_type="workflow_run",
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            resource_id=str(run.id),
            detail={"ready_nodes": ready_seen, "status": run.status, "worker_id": worker_id or "api"},
        )
    return run

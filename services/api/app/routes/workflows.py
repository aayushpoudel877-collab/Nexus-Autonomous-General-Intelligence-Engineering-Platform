from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ..core.dependencies import get_current_user, get_membership, require_roles
from ..db.session import get_db
from ..models import ResearchPlan, User, WorkbenchProject, WorkflowApproval, WorkflowDefinition, WorkflowNode, WorkflowNodeRun, WorkflowRun
from ..schemas.workflow import WorkflowApprovalDecision, WorkflowCreate, WorkflowRead, WorkflowRunCreate, WorkflowRunRead
from ..services.audit import record_audit
from ..services.workflow import build_workflow_policy_snapshot, ready_node_keys, validate_workflow_graph

router=APIRouter(prefix="/workflows",tags=["durable-workflows"])

async def _workflow(db, workflow_id, org_id):
    row=await db.scalar(select(WorkflowDefinition).options(selectinload(WorkflowDefinition.nodes)).where(WorkflowDefinition.id==workflow_id,WorkflowDefinition.organization_id==org_id))
    if not row: raise HTTPException(404,"Workflow not found")
    return row

@router.get("",response_model=list[WorkflowRead])
async def list_workflows(user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    m=await get_membership(user,db); rows=await db.scalars(select(WorkflowDefinition).options(selectinload(WorkflowDefinition.nodes)).where(WorkflowDefinition.organization_id==m.organization_id).order_by(WorkflowDefinition.updated_at.desc()).limit(100)); return list(rows.all())

@router.post("",response_model=WorkflowRead,status_code=201)
async def create_workflow(payload:WorkflowCreate,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    m=await get_membership(user,db)
    if payload.workbench_project_id and not await db.scalar(select(WorkbenchProject).where(WorkbenchProject.id==payload.workbench_project_id,WorkbenchProject.organization_id==m.organization_id)): raise HTTPException(404,"Workbench project not found")
    if payload.research_plan_id and not await db.scalar(select(ResearchPlan).where(ResearchPlan.id==payload.research_plan_id,ResearchPlan.organization_id==m.organization_id)): raise HTTPException(404,"Research plan not found")
    nodes=[n.model_dump() for n in payload.nodes]
    try: validate_workflow_graph(nodes)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    wf=WorkflowDefinition(organization_id=m.organization_id,owner_id=user.id,workbench_project_id=payload.workbench_project_id,research_plan_id=payload.research_plan_id,name=payload.name.strip(),description=payload.description.strip(),status="active")
    db.add(wf); await db.flush()
    for node in nodes: db.add(WorkflowNode(workflow_id=wf.id,**node))
    await record_audit(db,action="workflow.created",resource_type="workflow",resource_id=str(wf.id),actor_user_id=user.id,organization_id=m.organization_id,detail={"node_count":len(nodes)})
    await db.commit(); return await _workflow(db,wf.id,m.organization_id)

@router.get("/{workflow_id}",response_model=WorkflowRead)
async def get_workflow(workflow_id:UUID,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    m=await get_membership(user,db); return await _workflow(db,workflow_id,m.organization_id)

@router.post("/{workflow_id}/runs",response_model=WorkflowRunRead,status_code=201)
async def create_run(workflow_id:UUID,payload:WorkflowRunCreate,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    m=await get_membership(user,db); wf=await _workflow(db,workflow_id,m.organization_id)
    run=WorkflowRun(workflow_id=wf.id,organization_id=m.organization_id,created_by=user.id,status="queued",input_json=payload.input_json,context_json={},policy_snapshot=build_workflow_policy_snapshot())
    db.add(run); await db.flush()
    for node in wf.nodes: db.add(WorkflowNodeRun(run_id=run.id,node_id=node.id,status="pending",input_json=payload.input_json if not node.depends_on else {},output_json={},error_message=""))
    await record_audit(db,action="workflow.run.queued",resource_type="workflow_run",resource_id=str(run.id),actor_user_id=user.id,organization_id=m.organization_id,detail={"workflow_id":str(wf.id)})
    await db.commit()
    return await _run(db,run.id,m.organization_id)

async def _run(db,run_id,org_id):
    row=await db.scalar(select(WorkflowRun).options(selectinload(WorkflowRun.node_runs),selectinload(WorkflowRun.approvals)).where(WorkflowRun.id==run_id,WorkflowRun.organization_id==org_id));
    if not row: raise HTTPException(404,"Workflow run not found")
    return row

@router.get("/{workflow_id}/runs",response_model=list[WorkflowRunRead])
async def list_runs(workflow_id:UUID,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    m=await get_membership(user,db); await _workflow(db,workflow_id,m.organization_id); rows=await db.scalars(select(WorkflowRun).options(selectinload(WorkflowRun.node_runs),selectinload(WorkflowRun.approvals)).where(WorkflowRun.workflow_id==workflow_id,WorkflowRun.organization_id==m.organization_id).order_by(WorkflowRun.created_at.desc()).limit(100)); return list(rows.all())

@router.post("/runs/{run_id}/tick",response_model=WorkflowRunRead)
async def tick_run(run_id:UUID,user:User=Depends(get_current_user),db:AsyncSession=Depends(get_db)):
    m=await get_membership(user,db); run=await _run(db,run_id,m.organization_id); wf=await _workflow(db,run.workflow_id,m.organization_id); node_map={str(n.id):n for n in wf.nodes}; status_by_key={str(node_map[str(nr.node_id)].node_key):nr.status for nr in run.node_runs}
    for nr in run.node_runs:
        node=node_map[str(nr.node_id)]
        if nr.status=="pending" and all(status_by_key.get(dep)=="succeeded" for dep in node.depends_on):
            nr.status="ready"
    if run.status=="queued": run.status="running"; run.started_at=datetime.now(timezone.utc)
    await db.commit(); return await _run(db,run.id,m.organization_id)

@router.post("/runs/{run_id}/approvals/{approval_id}",response_model=WorkflowRunRead)
async def decide_approval(run_id:UUID,approval_id:UUID,payload:WorkflowApprovalDecision,user:User=Depends(require_roles("owner","admin")),db:AsyncSession=Depends(get_db)):
    m=await get_membership(user,db); approval=await db.scalar(select(WorkflowApproval).join(WorkflowRun).where(WorkflowApproval.id==approval_id,WorkflowApproval.run_id==run_id,WorkflowRun.organization_id==m.organization_id))
    if not approval: raise HTTPException(404,"Workflow approval not found")
    if approval.status!="pending": raise HTTPException(409,"Approval has already been decided")
    approval.status=payload.status; approval.decision_note=payload.note; approval.decided_by=user.id; approval.decided_at=datetime.now(timezone.utc)
    run=await db.scalar(select(WorkflowRun).where(WorkflowRun.id==run_id,WorkflowRun.organization_id==m.organization_id));
    if payload.status=="rejected": run.status="failed"
    else: run.status="running"
    await record_audit(db,action=f"workflow.approval.{payload.status}",resource_type="workflow_approval",resource_id=str(approval.id),actor_user_id=user.id,organization_id=m.organization_id,detail={"run_id":str(run.id)})
    await db.commit(); return await _run(db,run.id,m.organization_id)

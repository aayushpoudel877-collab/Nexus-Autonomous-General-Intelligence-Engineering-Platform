from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"
    __table_args__ = (Index("ix_workflow_definitions_org_status", "organization_id", "status"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    workbench_project_id: Mapped[UUID | None] = mapped_column(ForeignKey("workbench_projects.id", ondelete="SET NULL"), nullable=True, index=True)
    research_plan_id: Mapped[UUID | None] = mapped_column(ForeignKey("research_plans.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    nodes: Mapped[list["WorkflowNode"]] = relationship(back_populates="workflow", cascade="all, delete-orphan", order_by="WorkflowNode.created_at")
    runs: Mapped[list["WorkflowRun"]] = relationship(back_populates="workflow", cascade="all, delete-orphan")


class WorkflowNode(Base):
    __tablename__ = "workflow_nodes"
    __table_args__ = (UniqueConstraint("workflow_id", "node_key", name="uq_workflow_nodes_workflow_key"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_definitions.id", ondelete="CASCADE"), index=True)
    node_key: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(200))
    node_type: Mapped[str] = mapped_column(String(40))
    depends_on: Mapped[list[str]] = mapped_column(JSON, default=list)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    workflow: Mapped["WorkflowDefinition"] = relationship(back_populates="nodes")
    node_runs: Mapped[list["WorkflowNodeRun"]] = relationship(back_populates="node")


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (\n        CheckConstraint("attempt_count >= 0", name="ck_workflow_runs_attempt_count"),\n        Index("ix_workflow_runs_org_status", "organization_id", "status"),\n        Index("ix_workflow_runs_workflow_created", "workflow_id", "created_at"),\n        Index("ix_workflow_runs_claimable_lease", "status", "lease_expires_at"),\n    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_definitions.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    context_json: Mapped[dict] = mapped_column(JSON, default=dict)
    policy_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    workflow: Mapped["WorkflowDefinition"] = relationship(back_populates="runs")
    node_runs: Mapped[list["WorkflowNodeRun"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    approvals: Mapped[list["WorkflowApproval"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class WorkflowNodeRun(Base):
    __tablename__ = "workflow_node_runs"
    __table_args__ = (UniqueConstraint("run_id", "node_id", name="uq_workflow_node_runs_run_node"), Index("ix_workflow_node_runs_status_lease", "status", "lease_expires_at"))

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_nodes.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    run: Mapped["WorkflowRun"] = relationship(back_populates="node_runs")
    node: Mapped["WorkflowNode"] = relationship(back_populates="node_runs")
    approvals: Mapped[list["WorkflowApproval"]] = relationship(back_populates="node_run", cascade="all, delete-orphan")


class WorkflowApproval(Base):
    __tablename__ = "workflow_approvals"
    __table_args__ = (Index("ix_workflow_approvals_run_status", "run_id", "status"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"), index=True)
    node_run_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_node_runs.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    prompt: Mapped[str] = mapped_column(Text)
    decided_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decision_note: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    run: Mapped["WorkflowRun"] = relationship(back_populates="approvals")
    node_run: Mapped["WorkflowNodeRun"] = relationship(back_populates="approvals")

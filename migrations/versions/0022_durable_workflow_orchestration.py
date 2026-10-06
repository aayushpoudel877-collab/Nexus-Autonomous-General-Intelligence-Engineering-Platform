"""Add durable autonomous workflow orchestration state."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0022_durable_workflow_orchestration"
down_revision = "0021_secret_reference_binding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workbench_project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workbench_projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("research_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("research_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflow_definitions_organization_id", "workflow_definitions", ["organization_id"])
    op.create_index("ix_workflow_definitions_owner_id", "workflow_definitions", ["owner_id"])
    op.create_index("ix_workflow_definitions_workbench_project_id", "workflow_definitions", ["workbench_project_id"])
    op.create_index("ix_workflow_definitions_research_plan_id", "workflow_definitions", ["research_plan_id"])
    op.create_index("ix_workflow_definitions_org_status", "workflow_definitions", ["organization_id", "status"])

    op.create_table(
        "workflow_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_key", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("node_type", sa.String(length=40), nullable=False),
        sa.Column("depends_on", sa.JSON(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workflow_id", "node_key", name="uq_workflow_nodes_workflow_key"),
    )
    op.create_index("ix_workflow_nodes_workflow_id", "workflow_nodes", ["workflow_id"])

    op.create_table(
        "workflow_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("worker_id", sa.String(length=160), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.CheckConstraint("attempt_count >= 0", name="ck_workflow_runs_attempt_count"),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("policy_snapshot", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflow_runs_workflow_id", "workflow_runs", ["workflow_id"])
    op.create_index("ix_workflow_runs_organization_id", "workflow_runs", ["organization_id"])
    op.create_index("ix_workflow_runs_created_by", "workflow_runs", ["created_by"])
    op.create_index("ix_workflow_runs_worker_id", "workflow_runs", ["worker_id"])
    op.create_index("ix_workflow_runs_lease_expires_at", "workflow_runs", ["lease_expires_at"])
    op.create_index("ix_workflow_runs_org_status", "workflow_runs", ["organization_id", "status"])
    op.create_index("ix_workflow_runs_claimable_lease", "workflow_runs", ["status", "lease_expires_at"])
    op.create_index("ix_workflow_runs_workflow_created", "workflow_runs", ["workflow_id", "created_at"])

    op.create_table(
        "workflow_node_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("output_json", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("run_id", "node_id", name="uq_workflow_node_runs_run_node"),
    )
    op.create_index("ix_workflow_node_runs_run_id", "workflow_node_runs", ["run_id"])
    op.create_index("ix_workflow_node_runs_node_id", "workflow_node_runs", ["node_id"])
    op.create_index("ix_workflow_node_runs_status_lease", "workflow_node_runs", ["status", "lease_expires_at"])

    op.create_table(
        "workflow_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_node_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("node_run_id", name="uq_workflow_approval_node_run"),
    )
    op.create_index("ix_workflow_approvals_run_id", "workflow_approvals", ["run_id"])
    op.create_index("ix_workflow_approvals_node_run_id", "workflow_approvals", ["node_run_id"])
    op.create_index("ix_workflow_approvals_run_status", "workflow_approvals", ["run_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_workflow_approvals_run_status", table_name="workflow_approvals")
    op.drop_constraint("uq_workflow_approval_node_run", "workflow_approvals", type_="unique")
    op.drop_index("ix_workflow_approvals_node_run_id", table_name="workflow_approvals")
    op.drop_index("ix_workflow_approvals_run_id", table_name="workflow_approvals")
    op.drop_table("workflow_approvals")
    op.drop_index("ix_workflow_node_runs_status_lease", table_name="workflow_node_runs")
    op.drop_index("ix_workflow_node_runs_node_id", table_name="workflow_node_runs")
    op.drop_index("ix_workflow_node_runs_run_id", table_name="workflow_node_runs")
    op.drop_table("workflow_node_runs")
    op.drop_index("ix_workflow_runs_claimable_lease", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_org_status", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_lease_expires_at", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_worker_id", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_workflow_created", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_created_by", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_organization_id", table_name="workflow_runs")
    op.drop_index("ix_workflow_runs_workflow_id", table_name="workflow_runs")
    op.drop_table("workflow_runs")
    op.drop_index("ix_workflow_nodes_workflow_id", table_name="workflow_nodes")
    op.drop_table("workflow_nodes")
    op.drop_index("ix_workflow_definitions_org_status", table_name="workflow_definitions")
    op.drop_index("ix_workflow_definitions_research_plan_id", table_name="workflow_definitions")
    op.drop_index("ix_workflow_definitions_workbench_project_id", table_name="workflow_definitions")
    op.drop_index("ix_workflow_definitions_owner_id", table_name="workflow_definitions")
    op.drop_index("ix_workflow_definitions_organization_id", table_name="workflow_definitions")
    op.drop_table("workflow_definitions")

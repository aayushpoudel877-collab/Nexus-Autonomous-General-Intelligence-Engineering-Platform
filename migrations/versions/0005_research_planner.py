"""Autonomous research plans and dependency-aware tasks."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_research_planner"
down_revision = "0004_workbench"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "research_plans",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("organization_id", uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workbench_project_id", uuid, sa.ForeignKey("workbench_projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_research_plans_organization_id", "research_plans", ["organization_id"])
    op.create_index("ix_research_plans_owner_id", "research_plans", ["owner_id"])
    op.create_index("ix_research_plans_workbench_project_id", "research_plans", ["workbench_project_id"])

    op.create_table(
        "research_tasks",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("plan_id", uuid, sa.ForeignKey("research_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("task_type", sa.String(40), nullable=False, server_default="analysis"),
        sa.Column("status", sa.String(20), nullable=False, server_default="planned"),
        sa.Column("depends_on", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("output_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_research_tasks_plan_id", "research_tasks", ["plan_id"])


def downgrade() -> None:
    op.drop_index("ix_research_tasks_plan_id", table_name="research_tasks")
    op.drop_table("research_tasks")
    op.drop_index("ix_research_plans_workbench_project_id", table_name="research_plans")
    op.drop_index("ix_research_plans_owner_id", table_name="research_plans")
    op.drop_index("ix_research_plans_organization_id", table_name="research_plans")
    op.drop_table("research_plans")

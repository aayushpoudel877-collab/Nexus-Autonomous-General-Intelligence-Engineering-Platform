"""AI engineering workbench projects, datasets and experiments."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_workbench"
down_revision = "0003_ai_tutor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "workbench_projects",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "organization_id",
            uuid,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("task_type", sa.String(40), nullable=False, server_default="classification"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workbench_projects_organization_id", "workbench_projects", ["organization_id"])
    op.create_index("ix_workbench_projects_owner_id", "workbench_projects", ["owner_id"])

    op.create_table(
        "workbench_datasets",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "project_id",
            uuid,
            sa.ForeignKey("workbench_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_uri", sa.String(2048), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("schema_summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workbench_datasets_project_id", "workbench_datasets", ["project_id"])

    op.create_table(
        "workbench_experiments",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "project_id",
            uuid,
            sa.ForeignKey("workbench_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dataset_id",
            uuid,
            sa.ForeignKey("workbench_datasets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("algorithm", sa.String(120), nullable=False, server_default="baseline"),
        sa.Column("status", sa.String(20), nullable=False, server_default="planned"),
        sa.Column("parameters", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workbench_experiments_project_id", "workbench_experiments", ["project_id"])
    op.create_index("ix_workbench_experiments_dataset_id", "workbench_experiments", ["dataset_id"])


def downgrade() -> None:
    op.drop_index("ix_workbench_experiments_dataset_id", table_name="workbench_experiments")
    op.drop_index("ix_workbench_experiments_project_id", table_name="workbench_experiments")
    op.drop_table("workbench_experiments")
    op.drop_index("ix_workbench_datasets_project_id", table_name="workbench_datasets")
    op.drop_table("workbench_datasets")
    op.drop_index("ix_workbench_projects_owner_id", table_name="workbench_projects")
    op.drop_index("ix_workbench_projects_organization_id", table_name="workbench_projects")
    op.drop_table("workbench_projects")

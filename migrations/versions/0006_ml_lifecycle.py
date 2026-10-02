"""Training runs, model registry records and evaluations."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_ml_lifecycle"
down_revision = "0005_research_planner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "ml_training_runs",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("project_id", uuid, sa.ForeignKey("workbench_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_id", uuid, sa.ForeignKey("workbench_datasets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("owner_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("algorithm", sa.String(120), nullable=False, server_default="baseline"),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("parameters", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ml_training_runs_project_id", "ml_training_runs", ["project_id"])
    op.create_index("ix_ml_training_runs_dataset_id", "ml_training_runs", ["dataset_id"])
    op.create_index("ix_ml_training_runs_owner_id", "ml_training_runs", ["owner_id"])

    op.create_table(
        "registered_models",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("project_id", uuid, sa.ForeignKey("workbench_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_training_run_id", uuid, sa.ForeignKey("ml_training_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_experiment_id", uuid, sa.ForeignKey("workbench_experiments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("framework", sa.String(80), nullable=False, server_default="unknown"),
        sa.Column("artifact_uri", sa.String(2048), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="candidate"),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("approval_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "name", "version", name="uq_registered_model_project_name_version"),
    )
    for column in ("project_id", "owner_id", "source_training_run_id", "source_experiment_id"):
        op.create_index(f"ix_registered_models_{column}", "registered_models", [column])

    op.create_table(
        "model_evaluations",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("model_id", uuid, sa.ForeignKey("registered_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evaluator", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("metrics", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("criteria", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_model_evaluations_model_id", "model_evaluations", ["model_id"])


def downgrade() -> None:
    op.drop_index("ix_model_evaluations_model_id", table_name="model_evaluations")
    op.drop_table("model_evaluations")
    for column in ("source_experiment_id", "source_training_run_id", "owner_id", "project_id"):
        op.drop_index(f"ix_registered_models_{column}", table_name="registered_models")
    op.drop_table("registered_models")
    for column in ("owner_id", "dataset_id", "project_id"):
        op.drop_index(f"ix_ml_training_runs_{column}", table_name="ml_training_runs")
    op.drop_table("ml_training_runs")

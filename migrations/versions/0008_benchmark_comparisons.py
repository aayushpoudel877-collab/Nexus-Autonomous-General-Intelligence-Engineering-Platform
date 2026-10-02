"""Record bounded baseline/candidate benchmark comparisons."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_benchmark_comparisons"
down_revision = "0007_multimodal_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "benchmark_comparisons",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("project_id", uuid, sa.ForeignKey("workbench_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("baseline_model_id", uuid, sa.ForeignKey("registered_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_model_id", uuid, sa.ForeignKey("registered_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("baseline_metrics", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("candidate_metrics", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("criteria", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("deltas", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("baseline_model_id <> candidate_model_id", name="ck_benchmark_distinct_models"),
        sa.CheckConstraint("status IN ('passed', 'needs_improvement')", name="ck_benchmark_status"),
    )
    for column in ("project_id", "owner_id", "baseline_model_id", "candidate_model_id"):
        op.create_index(f"ix_benchmark_comparisons_{column}", "benchmark_comparisons", [column])
    op.create_index("ix_benchmark_comparisons_project_created", "benchmark_comparisons", ["project_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_benchmark_comparisons_project_created", table_name="benchmark_comparisons")
    for column in ("candidate_model_id", "baseline_model_id", "owner_id", "project_id"):
        op.drop_index(f"ix_benchmark_comparisons_{column}", table_name="benchmark_comparisons")
    op.drop_table("benchmark_comparisons")

"""Add worker lease and bounded result state to execution requests."""

from alembic import op
import sqlalchemy as sa


revision = "0014_execution_worker_leases"
down_revision = "0013_release_manifest_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "execution_requests",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "execution_requests",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "execution_requests",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "execution_requests",
        sa.Column("result_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.add_column(
        "execution_requests",
        sa.Column("output_bytes", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "execution_requests",
        sa.Column("error_code", sa.String(length=100), nullable=True),
    )
    op.create_check_constraint(
        "ck_execution_request_attempt_count",
        "execution_requests",
        "attempt_count >= 0",
    )
    op.create_check_constraint(
        "ck_execution_request_output_bytes",
        "execution_requests",
        "output_bytes >= 0",
    )
    op.create_index(
        "ix_execution_requests_lease_expires_at",
        "execution_requests",
        ["lease_expires_at"],
    )
    op.create_index(
        "ix_execution_requests_claimable_lease",
        "execution_requests",
        ["status", "lease_expires_at"],
    )
    op.alter_column("execution_requests", "attempt_count", server_default=None)
    op.alter_column("execution_requests", "result_json", server_default=None)
    op.alter_column("execution_requests", "output_bytes", server_default=None)


def downgrade() -> None:
    op.drop_index(
        "ix_execution_requests_claimable_lease",
        table_name="execution_requests",
    )
    op.drop_index(
        "ix_execution_requests_lease_expires_at",
        table_name="execution_requests",
    )
    op.drop_constraint(
        "ck_execution_request_output_bytes",
        "execution_requests",
        type_="check",
    )
    op.drop_constraint(
        "ck_execution_request_attempt_count",
        "execution_requests",
        type_="check",
    )
    op.drop_column("execution_requests", "error_code")
    op.drop_column("execution_requests", "output_bytes")
    op.drop_column("execution_requests", "result_json")
    op.drop_column("execution_requests", "heartbeat_at")
    op.drop_column("execution_requests", "lease_expires_at")
    op.drop_column("execution_requests", "attempt_count")

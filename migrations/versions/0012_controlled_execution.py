"""Add the controlled execution request queue."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0012_controlled_execution"
down_revision = "0011_governed_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("entrypoint", sa.String(length=240), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("max_memory_mb", sa.Integer(), nullable=False),
        sa.Column("max_output_bytes", sa.Integer(), nullable=False),
        sa.Column("network_policy", sa.String(length=20), nullable=False),
        sa.Column("network_allowlist", sa.JSON(), nullable=False),
        sa.Column("policy_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("worker_id", sa.String(length=160), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["installation_id"], ["plugin_installations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_execution_request_org_idempotency",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_execution_request_status",
        ),
        sa.CheckConstraint(
            "network_policy IN ('none', 'allowlist')",
            name="ck_execution_request_network_policy",
        ),
    )
    op.create_index(
        "ix_execution_requests_organization_id",
        "execution_requests",
        ["organization_id"],
    )
    op.create_index(
        "ix_execution_requests_installation_id",
        "execution_requests",
        ["installation_id"],
    )
    op.create_index(
        "ix_execution_requests_requested_by_user_id",
        "execution_requests",
        ["requested_by_user_id"],
    )
    op.create_index(
        "ix_execution_requests_status",
        "execution_requests",
        ["status"],
    )
    op.create_index(
        "ix_execution_requests_worker_id",
        "execution_requests",
        ["worker_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_execution_requests_worker_id", table_name="execution_requests")
    op.drop_index("ix_execution_requests_status", table_name="execution_requests")
    op.drop_index(
        "ix_execution_requests_requested_by_user_id",
        table_name="execution_requests",
    )
    op.drop_index(
        "ix_execution_requests_installation_id",
        table_name="execution_requests",
    )
    op.drop_index(
        "ix_execution_requests_organization_id",
        table_name="execution_requests",
    )
    op.drop_table("execution_requests")

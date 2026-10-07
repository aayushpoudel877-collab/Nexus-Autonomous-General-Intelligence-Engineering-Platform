"""Add durable workflow event journal."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0023_workflow_event_journal"
down_revision = "0022_durable_workflow_orchestration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE workflow_event_sequence START WITH 1")
    op.create_table(
        "workflow_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "node_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_node_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "sequence",
            sa.BigInteger(),
            server_default=sa.text("nextval('workflow_event_sequence')"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("actor", sa.String(length=40), nullable=False, server_default="orchestrator"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflow_events_run_id", "workflow_events", ["run_id"])
    op.create_index("ix_workflow_events_node_run_id", "workflow_events", ["node_run_id"])
    op.create_index("ix_workflow_events_run_sequence", "workflow_events", ["run_id", "sequence"])
    op.create_index("ix_workflow_events_run_created", "workflow_events", ["run_id", "created_at"])
    op.create_index("ix_workflow_events_node_created", "workflow_events", ["node_run_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_workflow_events_node_created", table_name="workflow_events")
    op.drop_index("ix_workflow_events_run_created", table_name="workflow_events")
    op.drop_index("ix_workflow_events_run_sequence", table_name="workflow_events")
    op.drop_index("ix_workflow_events_node_run_id", table_name="workflow_events")
    op.drop_index("ix_workflow_events_run_id", table_name="workflow_events")
    op.drop_table("workflow_events")
    op.execute("DROP SEQUENCE workflow_event_sequence")

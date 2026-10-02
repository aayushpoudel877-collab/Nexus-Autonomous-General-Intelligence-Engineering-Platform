"""Add request correlation IDs to audit events."""

from alembic import op
import sqlalchemy as sa

revision = "0009_audit_request_ids"
down_revision = "0008_benchmark_comparisons"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_events", sa.Column("request_id", sa.String(64), nullable=True))
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_request_id", table_name="audit_events")
    op.drop_column("audit_events", "request_id")

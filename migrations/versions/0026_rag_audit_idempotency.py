"""Enforce idempotency for audited RAG tool execution request IDs."""
from alembic import op

revision = "0026_rag_audit_idem"
down_revision = "0025_rag_operator"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Request IDs are only unique for successful RAG tool-execution events.
    # Other audit event types may legitimately share a request ID.
    op.create_index(
        "uq_audit_rag_tool_request_id",
        "audit_events",
        ["organization_id", "request_id"],
        unique=True,
        postgresql_where=op.inline_literal("action = 'rag.tool_execution.completed' AND request_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_audit_rag_tool_request_id", table_name="audit_events")

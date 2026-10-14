"""Add RAG operator feedback and reindex approval queue."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0025_rag_operator"
down_revision = "0024_rag_corpus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("query_sha256", sa.String(64), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("rating", sa.String(16), nullable=False),
        sa.Column("note", sa.String(1000), nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False, server_default="new"),
        sa.Column("triaged_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("rating IN ('helpful', 'unhelpful')", name="ck_rag_feedback_rating"),
        sa.CheckConstraint("status IN ('new', 'triaged', 'resolved', 'ignored')", name="ck_rag_feedback_status"),
    )
    op.create_index("ix_rag_feedback_org_status_created", "rag_feedback", ["organization_id", "status", "created_at"])
    op.create_table(
        "rag_reindex_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending_approval"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('pending_approval', 'approved', 'rejected')", name="ck_rag_reindex_status"),
        sa.ForeignKeyConstraint(["document_id", "organization_id"], ["rag_documents.id", "rag_documents.organization_id"], ondelete="CASCADE", name="fk_rag_reindex_document_org"),
    )
    op.create_index("ix_rag_reindex_org_status_created", "rag_reindex_requests", ["organization_id", "status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_rag_reindex_org_status_created", table_name="rag_reindex_requests")
    op.drop_table("rag_reindex_requests")
    op.drop_index("ix_rag_feedback_org_status_created", table_name="rag_feedback")
    op.drop_table("rag_feedback")

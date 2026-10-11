"""Add persistent tenant-scoped RAG corpus."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0024_rag_corpus"
down_revision = "0023_workflow_event_journal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("source_uri", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("content_chars", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'archived', 'deleted')", name="ck_rag_documents_status"),
        sa.UniqueConstraint("organization_id", "content_sha256", name="uq_rag_documents_org_hash"),
    )
    op.create_index("ix_rag_documents_org_created", "rag_documents", ["organization_id", "created_at"])
    op.create_table(
        "rag_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rag_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_char", sa.BigInteger(), nullable=False),
        sa.Column("end_char", sa.BigInteger(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("ordinal >= 0", name="ck_rag_chunks_ordinal"),
        sa.CheckConstraint("start_char >= 0 AND end_char > start_char", name="ck_rag_chunks_offsets"),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_rag_chunks_document_ordinal"),
    )
    op.create_index("ix_rag_chunks_org_document", "rag_chunks", ["organization_id", "document_id"])


def downgrade() -> None:
    op.drop_index("ix_rag_chunks_org_document", table_name="rag_chunks")
    op.drop_table("rag_chunks")
    op.drop_index("ix_rag_documents_org_created", table_name="rag_documents")
    op.drop_table("rag_documents")

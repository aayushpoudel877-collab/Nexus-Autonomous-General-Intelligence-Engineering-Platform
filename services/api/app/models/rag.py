"""Persistent, tenant-scoped RAG corpus records."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, JSON, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class RAGDocument(Base):
    __tablename__ = "rag_documents"
    __table_args__ = (
        UniqueConstraint("organization_id", "content_sha256", name="uq_rag_documents_org_hash"),
        UniqueConstraint("id", "organization_id", name="uq_rag_documents_id_org"),
        CheckConstraint("status IN ('active', 'archived', 'deleted')", name="ck_rag_documents_status"),
        Index("ix_rag_documents_org_created", "organization_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_uri: Mapped[str] = mapped_column(String(2048), default="", nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_chars: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    chunks: Mapped[list["RAGChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class RAGChunk(Base):
    __tablename__ = "rag_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_rag_chunks_document_ordinal"),
        CheckConstraint("ordinal >= 0", name="ck_rag_chunks_ordinal"),
        CheckConstraint("start_char >= 0 AND end_char > start_char", name="ck_rag_chunks_offsets"),
        Index("ix_rag_chunks_org_document", "organization_id", "document_id"),
        ForeignKeyConstraint(
            ["document_id", "organization_id"],
            ["rag_documents.id", "rag_documents.organization_id"],
            ondelete="CASCADE",
            name="fk_rag_chunks_document_org",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_char: Mapped[int] = mapped_column(BigInteger, nullable=False)
    end_char: Mapped[int] = mapped_column(BigInteger, nullable=False)
    token_count: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    document: Mapped[RAGDocument] = relationship(back_populates="chunks")

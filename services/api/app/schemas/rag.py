"""Request and response contracts for the tenant-scoped RAG API."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RAGDocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=2_000_000)
    source_uri: str = Field(default="", max_length=2048)
    metadata: dict[str, Any] = Field(default_factory=dict)
    max_chars: int = Field(default=1200, ge=100, le=12_000)
    overlap: int = Field(default=160, ge=0, le=11_999)


class RAGDocumentRead(BaseModel):
    id: UUID
    title: str
    source_uri: str
    content_sha256: str
    content_chars: int
    status: Literal["active", "archived", "deleted"]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: Any) -> "RAGDocumentRead":
        return cls(
            id=record.id,
            title=record.title,
            source_uri=record.source_uri,
            content_sha256=record.content_sha256,
            content_chars=record.content_chars,
            status=record.status,
            metadata=record.metadata_json,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class RAGDocumentCreated(BaseModel):
    document: RAGDocumentRead
    created: bool


class RAGChunkRead(BaseModel):
    id: UUID
    document_id: UUID
    ordinal: int
    text: str
    start_char: int
    end_char: int
    token_count: int


class RAGQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class RAGEvidenceRead(BaseModel):
    evidence_id: str
    document_id: UUID
    chunk_id: UUID
    title: str
    source_uri: str
    text: str
    start_char: int
    end_char: int
    score: float


class RAGQueryResponse(BaseModel):
    query: str
    retrieval_mode: Literal["lexical"]
    evidence: list[RAGEvidenceRead]
    note: str

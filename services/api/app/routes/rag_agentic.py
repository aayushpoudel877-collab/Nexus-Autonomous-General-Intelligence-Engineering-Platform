"""Authenticated, tenant-scoped API boundary for audited agentic retrieval."""
import json
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.rag.agentic_retrieval import (
    AgenticRetrievalPolicy,
    RetrievalTool,
    ToolCall,
    ToolExecutionError,
    ToolPolicyError,
    ToolResult,
    execute_bounded_tool_plan_with_audit,
)
from services.rag.chunking import Chunk
from services.rag.persistence import build_database_tool_audit_writer
from services.rag.retrieval import hybrid_retrieve, pack_evidence

from ..core.dependencies import get_current_user, get_membership
from ..db.session import get_db
from ..models import RAGChunk, RAGDocument, User

router = APIRouter(prefix="/rag", tags=["rag-agentic"])


class AgenticRAGQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=5)
    character_ngram_weight: float = Field(default=0.0, ge=0.0, le=1.0, allow_inf_nan=False)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must contain non-whitespace characters")
        return value


class _LexicalSearchArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(ge=1, le=5)
    character_ngram_weight: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)


async def _lexical_search(
    tenant_id: str,
    arguments: dict[str, Any],
    *,
    db: AsyncSession,
) -> ToolResult:
    """Search only the authenticated tenant's active RAG corpus."""
    from uuid import UUID

    organization_id = UUID(tenant_id)
    rows = await db.execute(
        select(RAGChunk, RAGDocument)
        .join(
            RAGDocument,
            (RAGDocument.id == RAGChunk.document_id)
            & (RAGDocument.organization_id == RAGChunk.organization_id),
        )
        .where(
            RAGChunk.organization_id == organization_id,
            RAGDocument.organization_id == organization_id,
            RAGDocument.status == "active",
        )
        .order_by(RAGDocument.created_at.desc(), RAGChunk.ordinal.asc())
        .limit(2_000)
    )
    pairs = rows.all()
    chunks = [
        Chunk(
            chunk_id=str(chunk.id),
            document_id=str(document.id),
            tenant_id=tenant_id,
            text=chunk.text,
            start_char=chunk.start_char,
            end_char=chunk.end_char,
            ordinal=chunk.ordinal,
        )
        for chunk, document in pairs
    ]
    hits = hybrid_retrieve(
        arguments["query"],
        chunks,
        tenant_id=tenant_id,
        top_k=arguments["top_k"],
        character_ngram_weight=arguments["character_ngram_weight"],
    )
    documents = {str(document.id): document for _, document in pairs}
    evidence = pack_evidence(
        hits,
        document_titles={key: item.title for key, item in documents.items()},
        source_uris={key: item.source_uri for key, item in documents.items()},
    )
    payload = {
        "retrieval_mode": "lexical",
        "evidence": [
            {
                "evidence_id": item.evidence_id,
                "document_id": item.document_id,
                "chunk_id": item.chunk_id,
                "title": item.title,
                "source_uri": item.source_uri,
                "text": item.text,
                "start_char": item.start_char,
                "end_char": item.end_char,
                "score": item.score,
                "character_ngram_score": item.character_ngram_score,
            }
            for item in evidence
        ],
    }
    output = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return ToolResult(
        tenant_id=tenant_id,
        text=output,
        evidence_ids=tuple(item.evidence_id for item in evidence),
    )


@router.post("/agentic-query")
async def audited_agentic_query(
    payload: AgenticRAGQuery,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run one bounded read-only retrieval tool and persist metadata-only provenance."""
    membership = await get_membership(user, db)
    tenant_id = str(membership.organization_id)
    request_id = str(uuid4())

    async def search_executor(scope_tenant_id: str, arguments: dict[str, Any]) -> ToolResult:
        return await _lexical_search(scope_tenant_id, arguments, db=db)

    tool = RetrievalTool(
        name="lexical_search",
        executor=search_executor,
        argument_model=_LexicalSearchArguments,
        required_scopes=frozenset({"rag:read"}),
        max_calls=1,
        timeout_seconds=5.0,
        max_output_chars=20_000,
        read_only=True,
    )
    writer = build_database_tool_audit_writer(
        db,
        organization_id=membership.organization_id,
        actor_user_id=user.id,
        request_id=request_id,
    )
    plan = (
        ToolCall(
            "lexical_search",
            {
                "query": payload.query,
                "top_k": payload.top_k,
                "character_ngram_weight": payload.character_ngram_weight,
            },
        ),
    )
    try:
        records = await execute_bounded_tool_plan_with_audit(
            plan,
            tools={"lexical_search": tool},
            tenant_id=tenant_id,
            actor_scopes=frozenset({"rag:read"}),
            audit_writer=writer,
            policy=AgenticRetrievalPolicy(
                max_steps=1,
                max_total_output_chars=20_000,
                max_evidence_ids=5,
            ),
        )
        # Audit writer flushes into this request's transaction. Commit before returning.
        await db.commit()
    except ToolPolicyError as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail="Retrieval request violates tool policy") from exc
    except ToolExecutionError as exc:
        await db.rollback()
        raise HTTPException(status_code=503, detail="Retrieval or provenance audit failed") from exc
    except Exception:
        await db.rollback()
        raise

    result = json.loads(records[0].text) if records else {"retrieval_mode": "lexical", "evidence": []}
    return {
        "request_id": request_id,
        "query": payload.query,
        "retrieval_mode": result["retrieval_mode"],
        "evidence": result["evidence"],
        "provenance": [
            {
                "tool_name": record.tool_name,
                "content_sha256": record.content_sha256,
                "detector_version": record.detector_version,
                "injection_markers": list(record.injection_markers),
                "output_chars": record.output_chars,
                "evidence_count": len(record.evidence_ids),
                "untrusted": True,
            }
            for record in records
        ],
        "note": "Tool outputs are untrusted. Provenance metadata was committed before this response; raw tool output is not stored in the audit event.",
    }

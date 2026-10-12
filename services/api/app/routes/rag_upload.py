"""Multipart upload route for safe, bounded RAG document extraction."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import get_membership, require_roles
from ..db.session import get_db
from ..models import User
from ..services.audit import record_audit
from ..schemas.rag import RAGDocumentCreated, RAGDocumentRead
from services.rag.ingestion import DocumentExtractionError, MAX_UPLOAD_BYTES, extract_document
from services.rag.persistence import DocumentAlreadyArchived, ingest_document

router = APIRouter(prefix="/rag", tags=["rag-knowledge"])


@router.post("/documents/upload", response_model=RAGDocumentCreated, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=300),
    source_uri: str = Form(default="", max_length=2048),
    max_chars: int = Form(default=1200, ge=100, le=12_000),
    overlap: int = Form(default=160, ge=0, le=11_999),
    user: User = Depends(require_roles("owner", "admin", "instructor")),
    db: AsyncSession = Depends(get_db),
):
    """Extract a supported document and persist it with parser provenance."""
    if not file.filename:
        raise HTTPException(status_code=422, detail="A filename is required")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    try:
        extracted = extract_document(
            data,
            filename=file.filename,
            content_type=file.content_type,
            max_bytes=MAX_UPLOAD_BYTES,
        )
        membership = await get_membership(user, db)
        document, created = await ingest_document(
            db,
            organization_id=membership.organization_id,
            title=(title or extracted.filename)[:300],
            text=extracted.text,
            source_uri=source_uri,
            metadata={
                "ingestion": {
                    "filename": extracted.filename,
                    "media_type": extracted.media_type,
                    "parser": extracted.parser,
                    "byte_count": extracted.byte_count,
                    "extracted_chars": extracted.extracted_chars,
                }
            },
            max_chars=max_chars,
            overlap=overlap,
        )
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DocumentAlreadyArchived as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if created:
        await record_audit(
            db,
            action="rag.document.uploaded",
            resource_type="rag_document",
            actor_user_id=user.id,
            organization_id=membership.organization_id,
            resource_id=str(document.id),
            detail={
                "content_sha256": document.content_sha256,
                "content_chars": document.content_chars,
                "parser": extracted.parser,
                "media_type": extracted.media_type,
                "byte_count": extracted.byte_count,
            },
        )
    await db.commit()
    await db.refresh(document)
    return RAGDocumentCreated(document=RAGDocumentRead.from_record(document), created=created)

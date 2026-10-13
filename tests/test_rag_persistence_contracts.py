import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.exc import IntegrityError
from uuid import uuid4

from services.api.app.models.rag import RAGChunk, RAGDocument
from services.rag.persistence import (
    MAX_DOCUMENT_CHARS,
    MAX_METADATA_BYTES,
    DocumentAlreadyArchived,
    ingest_document,
    list_document_chunks,
    set_document_status,
)


class RagPersistenceContractTests(unittest.IsolatedAsyncioTestCase):
    def test_chunk_foreign_key_enforces_matching_organization(self):
        document_constraints = {constraint.name for constraint in RAGDocument.__table__.constraints}
        chunk_constraints = {constraint.name for constraint in RAGChunk.__table__.constraints}
        self.assertIn("uq_rag_documents_id_org", document_constraints)
        self.assertIn("fk_rag_chunks_document_org", chunk_constraints)

    async def test_rejects_empty_title_and_text_before_database_access(self):
        session = AsyncMock()
        with self.assertRaises(ValueError):
            await ingest_document(session, organization_id=uuid4(), title=" ", text="text")
        with self.assertRaises(ValueError):
            await ingest_document(session, organization_id=uuid4(), title="title", text=" ")
        session.scalar.assert_not_awaited()

    async def test_rejects_bad_types_and_oversized_inputs_before_database_access(self):
        session = AsyncMock()
        with self.assertRaises(ValueError):
            await ingest_document(session, organization_id=uuid4(), title=None, text="text")
        with self.assertRaises(TypeError):
            await ingest_document(session, organization_id=uuid4(), title="title", text="text", source_uri=None)
        with self.assertRaises(ValueError):
            await ingest_document(
                session, organization_id=uuid4(), title="title", text="x" * (MAX_DOCUMENT_CHARS + 1)
            )
        with self.assertRaises(ValueError):
            await ingest_document(session, organization_id=uuid4(), title="title", text="text", max_chars=99)
        session.scalar.assert_not_awaited()

    async def test_metadata_must_be_bounded_json(self):
        session = AsyncMock()
        with self.assertRaises(ValueError):
            await ingest_document(
                session, organization_id=uuid4(), title="title", text="text", metadata={"bad": object()}
            )
        with self.assertRaises(ValueError):
            await ingest_document(
                session, organization_id=uuid4(), title="title", text="text",
                metadata={"value": "x" * MAX_METADATA_BYTES},
            )
        session.scalar.assert_not_awaited()

    async def test_invalid_pagination_is_rejected(self):
        with self.assertRaises(ValueError):
            await list_document_chunks(AsyncMock(), organization_id=uuid4(), document_id=uuid4(), limit=0)
        with self.assertRaises(ValueError):
            await list_document_chunks(AsyncMock(), organization_id=uuid4(), document_id=uuid4(), offset=-1)

    async def test_invalid_lifecycle_state_is_rejected(self):
        with self.assertRaises(ValueError):
            await set_document_status(
                AsyncMock(), organization_id=uuid4(), document_id=uuid4(), status="purge"
            )

    async def test_lifecycle_update_is_tenant_scoped_and_rejects_resurrection(self):
        session = AsyncMock()
        session.execute.return_value.rowcount = 0
        changed = await set_document_status(
            session, organization_id=uuid4(), document_id=uuid4(), status="active"
        )
        self.assertFalse(changed)
        statement = session.execute.await_args.args[0]
        sql = str(statement)
        self.assertIn("rag_documents.organization_id", sql)
        self.assertIn("rag_documents.status IN", sql)

    async def test_concurrent_duplicate_ingestion_reuses_the_winning_document(self):
        session = AsyncMock()
        session.add = MagicMock()
        existing = SimpleNamespace(status="active")
        session.scalar.side_effect = [None, existing]
        session.flush.side_effect = [None, IntegrityError("insert", {}, Exception("unique conflict"))]
        session.begin_nested = MagicMock(return_value=AsyncMock())

        document, created = await ingest_document(
            session, organization_id=uuid4(), title="title", text="concurrent duplicate content"
        )

        self.assertIs(document, existing)
        self.assertFalse(created)
        self.assertEqual(session.scalar.await_count, 2)

    async def test_matching_archived_document_fails_closed(self):
        session = AsyncMock()
        session.scalar.return_value = SimpleNamespace(status="archived")
        with self.assertRaises(DocumentAlreadyArchived):
            await ingest_document(session, organization_id=uuid4(), title="title", text="valid content")

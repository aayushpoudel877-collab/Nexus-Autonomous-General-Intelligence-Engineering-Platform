import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from services.rag.persistence import (
    MAX_DOCUMENT_CHARS,
    MAX_METADATA_BYTES,
    DocumentAlreadyArchived,
    ingest_document,
    list_document_chunks,
    set_document_status,
)


class RagPersistenceContractTests(unittest.IsolatedAsyncioTestCase):
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
        with self.assertRaises(ValueError):
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
        compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
        self.assertIn("rag_documents.organization_id", compiled)
        self.assertIn("rag_documents.status IN ('active')", compiled)

    async def test_matching_archived_document_fails_closed(self):
        session = AsyncMock()
        session.scalar.return_value = SimpleNamespace(status="archived")
        with self.assertRaises(DocumentAlreadyArchived):
            await ingest_document(session, organization_id=uuid4(), title="title", text="valid content")

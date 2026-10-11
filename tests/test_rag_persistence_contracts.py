import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from services.rag.persistence import DocumentAlreadyArchived, ingest_document, list_document_chunks, set_document_status


class RagPersistenceContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_empty_title_and_text_before_database_access(self):
        session = AsyncMock()
        with self.assertRaises(ValueError):
            await ingest_document(session, organization_id=uuid4(), title=" ", text="text")
        with self.assertRaises(ValueError):
            await ingest_document(session, organization_id=uuid4(), title="title", text=" ")
        session.scalar.assert_not_awaited()

    async def test_invalid_pagination_is_rejected(self):
        with self.assertRaises(ValueError):
            await list_document_chunks(AsyncMock(), organization_id=uuid4(), document_id=uuid4(), limit=0)
        with self.assertRaises(ValueError):
            await list_document_chunks(AsyncMock(), organization_id=uuid4(), document_id=uuid4(), offset=-1)

    async def test_invalid_lifecycle_state_is_rejected(self):
        with self.assertRaises(ValueError):
            await set_document_status(AsyncMock(), organization_id=uuid4(), document_id=uuid4(), status="purge")

    async def test_matching_archived_document_fails_closed(self):
        session = AsyncMock()
        session.scalar.return_value = SimpleNamespace(status="archived")
        with self.assertRaises(DocumentAlreadyArchived):
            await ingest_document(session, organization_id=uuid4(), title="title", text="valid content")

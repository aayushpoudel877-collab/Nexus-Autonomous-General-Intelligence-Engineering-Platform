import unittest
from services.rag.chunking import chunk_text, normalize_text
from services.rag.retrieval import hybrid_retrieve, pack_evidence
from services.rag.grounding import validate_citations
from services.rag.evaluation import evaluate_retrieval

class RagCoreTests(unittest.TestCase):
    def setUp(self):
        self.a = chunk_text("RAG retrieves relevant evidence for an answer.\n\nEvidence should be cited.", "doc-a", "tenant-a", max_chars=38, overlap=8)
        self.b = chunk_text("Tenant isolation prevents cross-organization data leaks.", "doc-b", "tenant-b")

    def test_normalization(self):
        self.assertEqual(normalize_text(" hello   world\r\nnext "), "hello world\nnext")

    def test_chunk_bounds_and_offsets(self):
        chunks = chunk_text("abcdefghij" * 10, "doc", "t", max_chars=25, overlap=5)
        self.assertTrue(chunks)
        self.assertTrue(all(len(c.text) <= 25 for c in chunks))
        self.assertTrue(all(c.start_char < c.end_char for c in chunks))

    def test_tenant_isolation(self):
        hits = hybrid_retrieve("tenant isolation", self.a + self.b, tenant_id="tenant-a")
        self.assertTrue(all(h.chunk.tenant_id == "tenant-a" for h in hits))
        self.assertFalse(any(h.chunk.document_id == "doc-b" for h in hits))

    def test_retrieval_and_metrics(self):
        hits = hybrid_retrieve("relevant evidence cited", self.a, tenant_id="tenant-a", top_k=5)
        self.assertTrue(hits)
        metrics = evaluate_retrieval(hits, {hits[0].chunk.chunk_id})
        self.assertEqual(metrics.recall_at_k, 1.0)
        self.assertEqual(metrics.reciprocal_rank, 1.0)

    def test_citation_validation(self):
        hits = hybrid_retrieve("evidence cited", self.a, tenant_id="tenant-a")
        evidence = pack_evidence(hits)
        self.assertTrue(validate_citations("Grounded [E1]", evidence).valid)
        self.assertFalse(validate_citations("Invented [E99]", evidence).valid)
        self.assertFalse(validate_citations("No citations", evidence).valid)

    def test_empty_and_bad_inputs(self):
        self.assertEqual(chunk_text("  ", "doc", "tenant"), [])
        with self.assertRaises(ValueError):
            chunk_text("text", "doc", "tenant", max_chars=10, overlap=10)

if __name__ == "__main__":
    unittest.main()

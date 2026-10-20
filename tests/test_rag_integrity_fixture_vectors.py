"""Data-driven regression tests for the RAG source integrity contract."""
import json
from pathlib import Path
import unittest
from hashlib import sha256

from services.rag.source_integrity import verify_artifact

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "rag_integrity"


class IntegrityFixtureTests(unittest.TestCase):
    def test_all_regression_vectors(self):
        fixtures = sorted(FIXTURE_DIR.glob("case_*.json"))
        self.assertEqual(len(fixtures), 100, "expected the complete 100-vector corpus")
        for path in fixtures:
            with self.subTest(fixture=path.name):
                case = json.loads(path.read_text(encoding="utf-8"))
                expected = sha256(case["expected_content"].encode("utf-8")).hexdigest()
                observed = case.get("observed_content")
                receipt = verify_artifact(
                    case["artifact_id"],
                    expected,
                    None if observed is None else observed.encode("utf-8"),
                    max_bytes=case.get("max_bytes", 25 * 1024 * 1024),
                )
                self.assertEqual(receipt.status, case["expected_status"], case["scenario"])
                self.assertEqual(receipt.reason, case.get("expected_reason"), case["scenario"])

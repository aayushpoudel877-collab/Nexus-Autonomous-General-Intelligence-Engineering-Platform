"""Data-driven evidence provenance regression vectors."""
import json
from pathlib import Path

from services.rag.evidence_integrity import (
    CitationItem,
    EvidenceItem,
    validate_evidence_bundle,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "rag_evidence_integrity"


def test_all_evidence_provenance_vectors():
    fixtures = sorted(FIXTURE_DIR.glob("case_*.json"))
    assert len(fixtures) == 100, "expected all 100 evidence provenance vectors"
    for path in fixtures:
        case = json.loads(path.read_text(encoding="utf-8"))
        evidence = [EvidenceItem(**item) for item in case["evidence"]]
        citations = [CitationItem(**item) for item in case["citations"]]
        report = validate_evidence_bundle(evidence, citations)
        actual_codes = sorted(issue.code for issue in report.issues)
        assert actual_codes == sorted(case["expected_codes"]), case["scenario"]
        assert report.is_valid is (not case["expected_codes"]), case["scenario"]

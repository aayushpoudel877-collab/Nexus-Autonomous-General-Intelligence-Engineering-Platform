import math

import pytest

from services.rag.evidence_integrity import (
    CitationItem,
    EvidenceItem,
    validate_evidence_bundle,
)


def evidence(**overrides):
    values = {
        "evidence_id": "ev-1",
        "document_id": "doc-1",
        "chunk_id": "chunk-1",
        "text": "The retrieval result is grounded.",
        "source_uri": "https://example.test/source/1",
        "start_char": 0,
        "end_char": len("The retrieval result is grounded."),
        "score": 0.75,
    }
    values.update(overrides)
    return EvidenceItem(**values)


def test_accepts_consistent_evidence_and_exact_quote():
    item = evidence()
    report = validate_evidence_bundle(
        [item], [CitationItem(item.evidence_id, "retrieval result")]
    )
    assert report.is_valid
    assert report.issues == ()


@pytest.mark.parametrize(
    ("item", "code"),
    [
        (evidence(evidence_id=""), "blank_evidence_id"),
        (evidence(document_id=" "), "blank_identity_field"),
        (evidence(chunk_id=""), "blank_identity_field"),
        (evidence(text=""), "empty_evidence_text"),
        (evidence(source_uri=""), "invalid_source_uri"),
        (evidence(source_uri="bad\nuri"), "invalid_source_uri"),
        (evidence(start_char=-1), "invalid_offsets"),
        (evidence(end_char=0), "invalid_offsets"),
        (evidence(end_char=2), "offset_length_mismatch"),
        (evidence(score=float("nan")), "invalid_score"),
        (evidence(score=float("inf")), "invalid_score"),
        (evidence(score=-0.1), "invalid_score"),
        (evidence(score=1.1), "invalid_score"),
    ],
)
def test_rejects_invalid_evidence_fields(item, code):
    report = validate_evidence_bundle([item], [])
    assert code in {issue.code for issue in report.issues}
    assert not report.is_valid


def test_rejects_duplicate_evidence_ids():
    report = validate_evidence_bundle([evidence(), evidence(document_id="doc-2")], [])
    assert "duplicate_evidence_id" in {issue.code for issue in report.issues}


@pytest.mark.parametrize(
    ("citation", "code"),
    [
        (CitationItem("missing", "quote"), "unknown_evidence_reference"),
        (CitationItem("ev-1", ""), "empty_quote"),
        (CitationItem("ev-1", "not actually present"), "quote_not_in_evidence"),
    ],
)
def test_rejects_unverifiable_citations(citation, code):
    report = validate_evidence_bundle([evidence()], [citation])
    assert code in {issue.code for issue in report.issues}


def test_report_does_not_echo_private_source_or_quote_text():
    secret = "PRIVATE-CUSTOMER-DETAIL-94821"
    item = evidence(text=secret, end_char=len(secret))
    report = validate_evidence_bundle([item], [CitationItem("ev-1", "missing quote")])
    assert secret not in repr(report)
    assert "missing quote" not in repr(report)


def test_rejects_excessive_bundle_and_invalid_limits():
    item = evidence()
    with pytest.raises(ValueError, match="exceeds"):
        validate_evidence_bundle([item, item], [], max_evidence=1)
    with pytest.raises(ValueError, match="exceeds"):
        validate_evidence_bundle([item], [CitationItem("ev-1", "The"), CitationItem("ev-1", "The")], max_citations=1)
    with pytest.raises(ValueError):
        validate_evidence_bundle([item], [], max_quote_chars=0)


def test_accepts_boundary_scores_and_quotes():
    item = evidence(score=0.0)
    report = validate_evidence_bundle([item], [CitationItem("ev-1", "The")])
    assert report.is_valid
    assert math.isfinite(item.score)
    assert evidence(score=1.0).score == 1.0

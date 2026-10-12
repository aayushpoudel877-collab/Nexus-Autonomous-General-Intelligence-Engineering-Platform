from __future__ import annotations

import pytest

from services.rag.grounding import (
    ClaimEvidence,
    GroundingClaim,
    LexicalGroundingVerifier,
)


def claim(text: str, citations: tuple[str, ...] = ("E1",), claim_id: str = "C1"):
    return GroundingClaim(claim_id, text, citations)


def evidence(text: str, evidence_id: str = "E1"):
    return ClaimEvidence(evidence_id, text)


def test_exact_lexical_support_is_reported_with_explicit_limit():
    report = LexicalGroundingVerifier().assess(
        [claim("The platform supports encrypted storage")],
        [evidence("The platform supports encrypted storage")],
    )
    item = report.assessments[0]
    assert item.status == "grounded"
    assert item.matched_evidence_ids == ("E1",)
    assert item.best_token_coverage == 1.0
    assert "semantic entailment is not verified" in item.reason
    assert report.should_abstain is False


def test_low_overlap_is_unsupported_and_causes_abstention():
    report = LexicalGroundingVerifier().assess(
        [claim("Penguins operate underwater elevators")],
        [evidence("The platform supports encrypted storage")],
    )
    assert report.assessments[0].status == "unsupported"
    assert report.unsupported_count == 1
    assert report.should_abstain is True


def test_intermediate_overlap_is_inconclusive():
    report = LexicalGroundingVerifier().assess(
        [claim("platform supports encrypted database storage")],
        [evidence("platform database storage")],
    )
    assert report.assessments[0].status == "inconclusive"
    assert report.inconclusive_count == 1
    assert report.should_abstain is True


def test_negation_mismatch_is_flagged_as_potential_contradiction():
    report = LexicalGroundingVerifier().assess(
        [claim("The system is not secure")],
        [evidence("The system is secure")],
    )
    assert report.assessments[0].status == "contradictory"
    assert report.contradictory_count == 1
    assert report.should_abstain is True


def test_missing_citations_are_unsupported():
    report = LexicalGroundingVerifier().assess(
        [claim("The platform supports encrypted storage", citations=())],
        [evidence("The platform supports encrypted storage")],
    )
    assert report.assessments[0].status == "unsupported"
    assert report.citation_coverage == 0.0


def test_claim_can_be_supported_by_one_of_multiple_citations():
    report = LexicalGroundingVerifier().assess(
        [claim("The platform supports encrypted storage", ("E1", "E2"))],
        [
            evidence("A completely unrelated source", "E1"),
            evidence("The platform supports encrypted storage", "E2"),
        ],
    )
    assert report.assessments[0].status == "grounded"
    assert report.assessments[0].matched_evidence_ids == ("E2",)
    assert report.citation_coverage == 1.0


def test_unknown_citation_fails_closed():
    with pytest.raises(ValueError, match="unknown evidence"):
        LexicalGroundingVerifier().assess(
            [claim("The platform supports encrypted storage", ("E-UNKNOWN",))],
            [evidence("The platform supports encrypted storage")],
        )


def test_duplicate_claim_and_evidence_ids_are_rejected():
    verifier = LexicalGroundingVerifier()
    with pytest.raises(ValueError, match="claim IDs"):
        verifier.assess(
            [claim("One claim", claim_id="C1"), claim("Another claim", claim_id="C1")],
            [evidence("One claim")],
        )
    with pytest.raises(ValueError, match="evidence IDs"):
        verifier.assess(
            [claim("One claim")],
            [evidence("One claim"), evidence("Duplicate ID")],
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"grounded_threshold": 0},
        {"grounded_threshold": 1.1},
        {"grounded_threshold": float("nan")},
        {"grounded_threshold": 0.5, "unsupported_threshold": 0.5},
        {"grounded_threshold": 0.5, "unsupported_threshold": float("nan")},
    ],
)
def test_thresholds_are_validated(kwargs):
    with pytest.raises(ValueError):
        LexicalGroundingVerifier(**kwargs)


def test_empty_claim_set_has_zero_metrics_and_abstains():
    report = LexicalGroundingVerifier().assess([], [evidence("Any source")])
    assert report.claim_count == 0
    assert report.citation_coverage == 0.0
    assert report.grounding_rate == 0.0
    assert report.should_abstain is True


def test_report_metrics_cover_all_claim_statuses():
    report = LexicalGroundingVerifier().assess(
        [
            claim("The platform supports encrypted storage", ("E1",), "C1"),
            claim("Penguins operate underwater elevators", ("E1",), "C2"),
            claim("platform supports database encryption", ("E1",), "C3"),
            claim("The system is not secure", ("E2",), "C4"),
        ],
        [
            evidence("The platform supports encrypted storage", "E1"),
            evidence("The system is secure", "E2"),
        ],
    )
    assert report.claim_count == 4
    assert report.grounded_count == 1
    assert report.unsupported_count == 1
    assert report.inconclusive_count == 1
    assert report.contradictory_count == 1
    assert report.citation_coverage == 1.0
    assert report.grounding_rate == 0.25
    assert report.should_abstain is True

from services.rag.grounding import evidence_prompt_block, validate_citations
from services.rag.retrieval import Evidence


def sample_evidence(evidence_id="E1"):
    return Evidence(
        evidence_id=evidence_id,
        document_id="doc-1",
        chunk_id="chunk-1",
        title="Reference",
        text="The system is secure.",
        source_uri="https://example.test/reference",
        start_char=0,
        end_char=20,
        score=0.9,
    )


def test_structural_citation_validation_accepts_only_supplied_ids():
    report = validate_citations("The system is secure [E1].", [sample_evidence()])
    assert report.valid is True
    assert report.cited_evidence == ("E1",)
    assert report.unknown_citations == ()


def test_structural_citation_validation_rejects_unknown_ids():
    report = validate_citations("The system is secure [E2].", [sample_evidence()])
    assert report.valid is False
    assert report.unknown_citations == ("E2",)


def test_structural_citation_validation_can_allow_uncited_text():
    report = validate_citations("No citation.", [sample_evidence()], require_citation=False)
    assert report.valid is True
    assert report.has_citation is False


def test_evidence_prompt_block_labels_sources_as_untrusted_data():
    rendered = evidence_prompt_block([sample_evidence()])
    assert "untrusted reference material" in rendered
    assert "[E1] Source: Reference" in rendered
    assert "The system is secure." in rendered

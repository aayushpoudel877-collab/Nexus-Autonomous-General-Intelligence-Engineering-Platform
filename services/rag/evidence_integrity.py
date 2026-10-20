"""Validate that RAG answer citations point to real, consistent retrieved evidence.

This module is provider-agnostic and intentionally returns reason codes rather than
copying source text into diagnostics. It does not claim that a cited source is true.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from collections.abc import Iterable
from itertools import islice


MAX_EVIDENCE_ITEMS = 100
MAX_CITATION_ITEMS = 200
MAX_QUOTE_CHARS = 4_000
MAX_SOURCE_URI_CHARS = 2_048
MAX_EVIDENCE_TEXT_CHARS = 12_000


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    evidence_id: str
    document_id: str
    chunk_id: str
    text: str
    source_uri: str
    start_char: int
    end_char: int
    score: float


@dataclass(frozen=True, slots=True)
class CitationItem:
    evidence_id: str
    quote: str


@dataclass(frozen=True, slots=True)
class EvidenceIssue:
    code: str
    item_index: int
    field: str


@dataclass(frozen=True, slots=True)
class EvidenceValidationReport:
    is_valid: bool
    evidence_count: int
    citation_count: int
    issues: tuple[EvidenceIssue, ...]


def validate_evidence_bundle(
    evidence: Iterable[EvidenceItem],
    citations: Iterable[CitationItem],
    *,
    max_evidence: int = MAX_EVIDENCE_ITEMS,
    max_citations: int = MAX_CITATION_ITEMS,
    max_quote_chars: int = MAX_QUOTE_CHARS,
) -> EvidenceValidationReport:
    """Validate identity, offsets, score bounds, and citation-to-evidence links.

    Issues contain only stable codes, indices, and field names; raw source text and
    quoted material are never copied into the report. Inputs are bounded to avoid
    accidental unbounded work when validating model-generated output.
    """
    if not 1 <= max_evidence <= MAX_EVIDENCE_ITEMS:
        raise ValueError("max_evidence must be between 1 and 100")
    if not 1 <= max_citations <= MAX_CITATION_ITEMS:
        raise ValueError("max_citations must be between 1 and 200")
    if not 1 <= max_quote_chars <= MAX_QUOTE_CHARS:
        raise ValueError("max_quote_chars must be between 1 and 4000")

    evidence_items = list(islice(evidence, max_evidence + 1))
    citation_items = list(islice(citations, max_citations + 1))
    if len(evidence_items) > max_evidence:
        raise ValueError("evidence bundle exceeds max_evidence")
    if len(citation_items) > max_citations:
        raise ValueError("citation bundle exceeds max_citations")

    issues: list[EvidenceIssue] = []
    known: dict[str, EvidenceItem] = {}
    for index, item in enumerate(evidence_items):
        if not isinstance(item, EvidenceItem):
            issues.append(EvidenceIssue("invalid_evidence_item", index, "item"))
            continue
        if not isinstance(item.evidence_id, str) or not item.evidence_id.strip():
            issues.append(EvidenceIssue("blank_evidence_id", index, "evidence_id"))
        elif item.evidence_id in known:
            issues.append(EvidenceIssue("duplicate_evidence_id", index, "evidence_id"))
        else:
            known[item.evidence_id] = item

        for field_name, value in (
            ("document_id", item.document_id),
            ("chunk_id", item.chunk_id),
        ):
            if not isinstance(value, str) or not value.strip():
                issues.append(EvidenceIssue("blank_identity_field", index, field_name))

        if not isinstance(item.text, str) or not item.text:
            issues.append(EvidenceIssue("empty_evidence_text", index, "text"))
        elif len(item.text) > MAX_EVIDENCE_TEXT_CHARS:
            issues.append(EvidenceIssue("evidence_text_too_long", index, "text"))
        if (
            not isinstance(item.source_uri, str)
            or not item.source_uri.strip()
            or len(item.source_uri) > MAX_SOURCE_URI_CHARS
            or any(ord(character) < 32 for character in item.source_uri)
        ):
            issues.append(EvidenceIssue("invalid_source_uri", index, "source_uri"))

        if (
            not isinstance(item.start_char, int)
            or isinstance(item.start_char, bool)
            or not isinstance(item.end_char, int)
            or isinstance(item.end_char, bool)
            or item.start_char < 0
            or item.end_char <= item.start_char
        ):
            issues.append(EvidenceIssue("invalid_offsets", index, "offsets"))
        elif isinstance(item.text, str) and len(item.text) != item.end_char - item.start_char:
            issues.append(EvidenceIssue("offset_length_mismatch", index, "offsets"))

        if (
            isinstance(item.score, bool)
            or not isinstance(item.score, (int, float))
            or not math.isfinite(item.score)
            or not 0.0 <= item.score <= 1.0
        ):
            issues.append(EvidenceIssue("invalid_score", index, "score"))

    for index, citation in enumerate(citation_items):
        if not isinstance(citation, CitationItem):
            issues.append(EvidenceIssue("invalid_citation_item", index, "item"))
            continue
        if not isinstance(citation.evidence_id, str) or not citation.evidence_id.strip():
            issues.append(EvidenceIssue("unknown_evidence_reference", index, "evidence_id"))
            continue
        item = known.get(citation.evidence_id)
        if item is None:
            issues.append(EvidenceIssue("unknown_evidence_reference", index, "evidence_id"))
            continue
        if not isinstance(citation.quote, str) or not citation.quote.strip():
            issues.append(EvidenceIssue("empty_quote", index, "quote"))
        elif len(citation.quote) > max_quote_chars:
            issues.append(EvidenceIssue("quote_too_long", index, "quote"))
        elif not isinstance(item.text, str) or citation.quote not in item.text:
            issues.append(EvidenceIssue("quote_not_in_evidence", index, "quote"))

    return EvidenceValidationReport(
        is_valid=not issues,
        evidence_count=len(evidence_items),
        citation_count=len(citation_items),
        issues=tuple(issues),
    )

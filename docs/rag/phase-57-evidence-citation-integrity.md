# Phase 57 — RAG evidence and citation integrity

## Purpose

Validate the contract between retrieved evidence and citations generated for an answer before the answer is presented. The validator is provider-independent and does not make claims about the truth of a source.

## Validation guarantees

- Evidence IDs are present and unique within the bundle.
- Document and chunk identity fields are nonblank.
- Evidence text and source locators are present and bounded.
- Character offsets are nonnegative, ordered, and consistent with the supplied evidence text.
- Retrieval scores are finite normalized values between zero and one.
- Every citation references a known evidence ID.
- Every quote is nonempty, bounded, and an exact substring of its cited evidence.
- Diagnostic reports contain reason codes, field names, and indexes only; they do not echo source text or quotes.
- Bundle sizes are bounded (100 evidence records, 200 citations, 4,000 characters per quote).

## Files

- `services/rag/evidence_integrity.py` — typed records, bounded validator, and privacy-safe report.
- `tests/test_rag_evidence_integrity.py` — focused unit and adversarial tests.
- `tests/fixtures/rag_evidence_integrity/case_001.json` through `case_100.json` — 100 separately committed regression vectors.
- `tests/test_rag_evidence_fixture_vectors.py` — asserts all vectors and exact expected issue codes.

## Run

```bash
pytest tests/test_rag_evidence_integrity.py tests/test_rag_evidence_fixture_vectors.py
ruff check .
```

## Explicit limitations

This validates structural citation provenance and exact quoted-text membership. It cannot establish that the source itself is trustworthy, that the answer's reasoning is complete, or that a generated claim is entailed by the quote. Those require separate source-trust, entailment, and end-to-end answer evaluation stages.

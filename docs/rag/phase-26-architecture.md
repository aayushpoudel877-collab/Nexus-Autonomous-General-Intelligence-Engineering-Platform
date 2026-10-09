# Phase 26 — RAG Knowledge Intelligence Engine

## Goal
Add a reusable evidence-retrieval foundation to NEXUS-Ω without coupling the platform to one LLM, embedding model, or vector database.

## Data flow
1. **Ingest adapter (future):** authenticate source access, validate tenant ownership, parse supported formats, and produce canonical text.
2. **Normalization and chunking (implemented):** normalize whitespace, split bounded overlapping chunks, and preserve offsets in normalized text.
3. **Index adapters (future):** persist lexical postings and optional embeddings with model/version metadata.
4. **Retrieval (implemented core):** enforce tenant filter before scoring, compute lexical relevance, accept optional dense similarity scores, and combine them with a configurable weighted score.
5. **Evidence packer (implemented):** assign stable response-local evidence IDs and preserve source/document/chunk offsets.
6. **Generation adapter (future):** pass evidence to a configured model with instructions to abstain when unsupported and treat retrieved content as untrusted.
7. **Grounding checks (implemented structural layer):** reject unknown citation IDs. This does not prove that a claim is entailed by the cited passage.
8. **Evaluation (implemented primitives):** calculate retrieval recall and reciprocal rank, plus citation-structure coverage. Human-reviewed datasets and semantic entailment checks remain future work.

## Security and privacy invariants
- Tenant scoping occurs before retrieval scoring; API and storage layers must also enforce authorization.
- Source text is untrusted data and may contain prompt-injection attempts.
- Evidence IDs are response-local labels, not authorization tokens.
- Never log raw private document text by default; prefer opaque IDs and bounded metrics.
- Do not silently fetch arbitrary URLs. Connectors require explicit allowlists, timeouts, size limits, and SSRF defenses.
- Do not execute retrieved code or instructions.
- Model/provider calls must be opt-in, observable, budget-limited, and covered by data-retention policy.

## Failure modes
- Empty query/document: reject or return an empty result explicitly.
- No lexical match: return no lexical hits rather than fabricate evidence.
- Missing dense score: dense contribution is zero; it is not inferred.
- Unknown citation: fail the structural check.
- Retrieval hit with valid citation but unsupported claim: structural validation cannot detect it; use curated evaluation and human review.

## Operational metrics
Track latency by stage, documents/chunks indexed, empty-result rate, recall@k on curated queries, reciprocal rank, citation coverage, unknown-citation rate, tenant-scope rejection count, token/cost budgets, and provider error rates. Do not expose document contents in telemetry.

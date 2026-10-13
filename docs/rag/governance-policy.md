# RAG Data Governance Policy

This document is an engineering baseline, not a substitute for legal, privacy, security or records-management review.

## Data minimization
- Never place raw queries, prompts, retrieved passages, source documents, secrets, or authentication material in routine audit events.
- Use opaque identifiers and bounded numeric measurements; ensure identifiers themselves contain no personal data.
- Keep source content in the corpus store and lineage metadata separate.
- Treat source URIs and document titles as potentially sensitive; do not copy them into general telemetry.

## Tenant isolation
Every persistence query, index lookup, deletion, trace view and export must be scoped to the authenticated organization. A tenant identifier supplied by a caller must not override authenticated membership. Include organization scope in external-index keys and deletion idempotency keys.

## Deletion lifecycle
A logical deletion is not proof of physical erasure. Record a durable deletion request, dispatch it idempotently to each configured index, retry failures, and expose a failed/dead-letter state for operator review. Verify deletion by document/chunk identity and tenant. Apply the same policy to caches, derived embeddings, exports and backups according to documented backup expiry.

## Retention and legal holds
Configure retention windows by data class and jurisdiction. Before deleting, check applicable legal holds and contractual retention obligations. Log the policy version and outcome, not deleted content. Run periodic reconciliation to identify stale index entries. The helper in this repository computes expiry only; it does not perform deletion.

## Evaluation and model cards
Identify dataset provenance, language coverage, known gaps, intended use, limitations, owner and evaluation date. Distinguish synthetic contract fixtures from human-reviewed evidence. Require human approval before production promotion; do not treat a passing automated gate as authorization to deploy.

## Incident response
For suspected cross-tenant exposure or failed deletion, pause affected retrieval/index paths, preserve privacy-safe identifiers and timestamps, investigate access logs, and follow the organization's incident notification and remediation process.

# RAG Phase 36 — Operator Workbench

## Scope

This phase adds tenant-scoped ingestion health, privacy-conscious retrieval feedback, a feedback triage queue, and an approval queue for document reindex requests.

## Safety and data boundaries

- Every operator query is scoped to the authenticated user's active organization.
- Raw query text is not persisted in the feedback table; feedback stores a SHA-256 digest and evidence identifiers instead. A plain digest is not anonymization: low-entropy queries may be guessed, so the digest must still be treated as sensitive metadata.
- Feedback notes are bounded and should not contain secrets or unnecessary personal information.
- Reindex requests are limited to active documents and require owner/admin authorization to request and review.
- Approval is not execution. This phase records review decisions only; no vector index is modified and no reindex worker is launched.
- Retrieval remains lexical until a concrete embedding provider and durable vector index are integrated and evaluated.

## API

- `GET /api/v1/rag/operator/health` — organization-scoped document/chunk counts and pending-work counts.
- `POST /api/v1/rag/operator/feedback` — record helpful/unhelpful feedback with query digest and evidence IDs.
- `GET /api/v1/rag/operator/feedback` and `PATCH /api/v1/rag/operator/feedback/{id}` — role-gated triage.
- `POST /api/v1/rag/operator/documents/{id}/reindex` — request reindex review for an active same-organization document.
- `GET /api/v1/rag/operator/reindex-requests` and `PATCH /api/v1/rag/operator/reindex-requests/{id}` — inspect and approve/reject requests; only pending requests may be reviewed.

## Acceptance and remaining work

- PostgreSQL migration must upgrade/downgrade/re-upgrade cleanly.
- Contract tests cover request validation, authenticated route registration, and forward-only feedback triage transitions; the production CI migration job checks schema upgrade/downgrade/re-upgrade.
- The web workbench displays corpus health, runs retrieval diagnostics, supports feedback triage, and submits/reviews reindex requests. API database integration tests for tenant isolation and role boundaries remain a follow-up acceptance item.
- A durable reindex worker, actual vector-store integration, retrieval latency traces, telemetry dashboards, and broader reviewed datasets remain outside this phase's current implementation.


## Hardening update

- Feedback evidence identifiers are normalized and whitespace-only values are rejected.
- Feedback state changes are serialized with a row lock; terminal states cannot be moved backwards, and repeated same-state updates are idempotent.
- Audit events are flushed after generated resource IDs exist, so feedback and reindex request events can reference their resource IDs reliably.
- Requester self-approval is rejected for reindex requests. Approval remains a recorded decision only, not a command to execute indexing.

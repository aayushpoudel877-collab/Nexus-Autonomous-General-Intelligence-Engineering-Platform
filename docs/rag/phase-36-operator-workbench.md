# RAG Phase 36 — Operator Workbench

## Scope

This phase adds tenant-scoped ingestion health, privacy-conscious retrieval feedback, a feedback triage queue, and an approval queue for document reindex requests.

## Safety and data boundaries

- Every operator query is scoped to the authenticated user's active organization.
- Raw query text is hashed before persistence; feedback stores the digest and evidence identifiers, not the query itself.
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
- API tests must cover validation, tenant isolation, role boundaries, feedback privacy, and one-time reindex review.
- UI should display health, triage feedback, and request/review reindex operations.
- A durable reindex worker, actual vector-store integration, retrieval latency traces, telemetry dashboards, and broader reviewed datasets remain outside this phase's current implementation.

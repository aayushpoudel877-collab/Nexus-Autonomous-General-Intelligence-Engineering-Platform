# Phase 28 — Authenticated RAG API

## Goal
Expose the persistent RAG corpus through the existing FastAPI identity and organization-membership controls without allowing clients to choose their own tenant.

## Delivered endpoints
- `POST /api/v1/rag/documents` — instructor/admin/owner-only text ingestion; server derives organization from the authenticated membership; duplicate content is idempotent and returns HTTP 200 with `created: false`.
- `GET /api/v1/rag/documents` — tenant-scoped metadata listing with bounded pagination and optional lifecycle filter.
- `GET /api/v1/rag/documents/{document_id}/chunks` — bounded chunk listing for active documents within the current organization.
- `DELETE /api/v1/rag/documents/{document_id}` — role-gated soft deletion and audit event; corpus rows are not physically erased.
- `POST /api/v1/rag/query` — tenant-scoped lexical retrieval over active persisted chunks with evidence identifiers and source offsets.

## Security controls
- Every endpoint uses the current-user authentication dependency and resolves organization membership on the server.
- Request schemas reject extra fields, so a caller cannot pass an organization/tenant override.
- All document and chunk queries constrain organization IDs; retrieval joins documents to chunks on both document ID and organization ID.
- Ingestion and delete operations are restricted to owner/admin/instructor roles; reads and queries require authenticated membership.
- Text length, chunk settings, query length, result count and pagination are bounded.
- Document deletion is logical only. Physical deletion, retention enforcement and deletion propagation to future vector stores are not implemented yet.
- The query endpoint caps its lexical candidate set at 2,000 persisted chunks to bound memory use. This is a correctness/performance trade-off and not a substitute for a vector index.
- Source URI is stored and returned as provenance only. The server does not fetch it.
- No LLM generation or embedding provider is invoked. The response explicitly identifies lexical retrieval mode.

## Verification
CI checks include route registration, authenticated dependency presence, request validation, Python linting/tests and the frontend production build. Database integration tests with a real PostgreSQL service are still required to validate migration and tenant-isolation behavior end-to-end.

## Acceptance criteria
- No request-controlled tenant identifier is accepted.
- Cross-organization document identifiers resolve as not found.
- Retrieval only includes active records from the caller's organization.
- Writes are audited and role-gated.
- No external model or URL call occurs during ingestion/query.

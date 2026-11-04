# Phase 88 — RAG feedback queue pagination

## Goal

Make the operator feedback queue usable as the feedback corpus grows, without fetching every matching record in one request.

## API

`GET /api/v1/rag/operator/feedback/page?status=new&limit=25&offset=0` returns:
- A bounded page of feedback records for one allowed status.
- The total number of matching records for the active organization.
- The requested limit and offset.
- A `has_more` flag for forward navigation.

The endpoint requires owner, admin, or instructor role. Page size is bounded from 1 to 100 and offset from 0 to 1,000,000. Both the count query and page query are tenant-scoped. Ordering is deterministic: newest creation timestamp first, then ID ascending as a stable tie-breaker.

## Operator experience

The RAG Operator Workbench uses pages of 25 records, retains the status filters introduced in Phase 87, and provides previous/next navigation with a visible range and total count. Per-item lifecycle history remains available on each page.

## Validation

- OpenAPI bounds and authentication dependency checks.
- Tenant-scope assertions for both count and page queries.
- Deterministic ordering, limit/offset, and has-more behavior.
- Empty result handling.
- Full CI: Python checks, web production build, migrations, and container builds.

No schema migration is required. The existing list endpoint remains unchanged for compatibility.

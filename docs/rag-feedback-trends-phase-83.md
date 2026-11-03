# Phase 83 — RAG feedback activity trends

## Goal

Extend the Phase 82 aggregate insights with a bounded time-series view so workspace operators can understand whether user-reported retrieval feedback is changing over time.

## API

`GET /api/v1/rag/operator/feedback/trend?days=30` returns daily UTC buckets for a requested window from 7 through 90 days. Each bucket includes helpful, unhelpful, and total counts. Empty dates are included with zero counts.

The endpoint:
- Requires owner, admin, or instructor role.
- Resolves the active organization from authenticated membership and scopes every database query to that organization.
- Uses database-side aggregation rather than returning individual feedback rows.
- Returns only date/rating aggregates; no query digest, note, actor ID, or evidence identifier is exposed.
- Bounds the response to at most 90 daily buckets.

## Operator experience

The RAG Operator Workbench includes a 7/30/90-day selector and a compact daily activity chart. The chart distinguishes helpful and needs-improvement ratings and displays the total per day. The displayed timezone is explicitly UTC.

## Interpretation

These are user-reported usefulness ratings, not measures of factual correctness, answer faithfulness, or retrieval relevance. Sparse daily counts should not be over-interpreted. A zero-count day means no feedback was recorded, not that retrieval quality was good or bad.

## Validation

- OpenAPI route and parameter-bound checks.
- Authentication dependency contract.
- Unit coverage for tenant-scoped aggregation, zero-filled dates, and empty windows.
- Full CI: Python checks, web build, migrations, and container builds.

No schema migration is required; the endpoint aggregates the existing feedback table.

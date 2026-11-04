# Phase 84 — RAG feedback period comparison

## Goal

Extend the Phase 82 aggregate insights and Phase 83 daily trend with a fair, adjacent-period comparison. Operators can see whether the volume and mix of user-reported usefulness feedback changed over time without exposing individual feedback records.

## API

`GET /api/v1/rag/operator/feedback/compare?days=30` compares two adjacent, complete UTC windows. The `days` parameter is bounded from 7 through 90.

- The current window covers the most recent complete `days` calendar days, ending at today's UTC midnight (exclusive).
- The previous window is the immediately preceding interval of the same length.
- Both periods use database-side rating aggregation and active-organization scoping derived from authenticated membership.
- The response includes helpful, unhelpful, and total counts; helpful-rate percentages; absolute and relative count changes; and helpful-rate percentage-point change.
- A relative percentage change is `null` when the previous-period denominator is zero. A helpful-rate delta is `null` when either period has no feedback.
- Only aggregates and period boundaries are returned. Raw queries, query digests, notes, actors, and evidence IDs are excluded.

## Operator experience

The RAG Operator Workbench uses the existing 7/30/90-day selector to load the comparison. It displays current and previous totals, helpful and unhelpful counts, total response change, and helpful-rate percentage-point change. The comparison explicitly labels its complete UTC-day windows; the daily chart remains a separate view that includes its displayed date range.

## Interpretation and limitations

Feedback represents user-perceived usefulness, not factual correctness, semantic faithfulness, or a ground-truth retrieval label. Count changes can reflect participation as well as retrieval experience. Relative changes are intentionally unavailable when the baseline period has zero responses; the UI does not manufacture an infinite or misleading percentage.

## Validation

- OpenAPI route, bounded parameter, and authentication dependency checks.
- Tenant-scope assertions for both database aggregation queries.
- Adjacent-window boundary and duration checks.
- Rating-mix, helpful-rate, absolute-change, percentage-change, and zero-baseline tests.
- Full CI: Python checks, web production build, migrations, and container builds.

No schema migration is required. The feature reads existing `rag_feedback` rows and does not alter retrieval behavior.

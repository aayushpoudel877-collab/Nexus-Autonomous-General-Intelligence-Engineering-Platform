# Phase 86 — RAG feedback lifecycle analytics

## Goal

Extend feedback insights beyond submission volume to show the daily movement of feedback through the existing triage lifecycle.

## API

`GET /api/v1/rag/operator/feedback/lifecycle-trend?days=30` returns zero-filled daily UTC counts over a bounded 7–90 day window.

The endpoint aggregates existing `audit_events` for the `rag_feedback` resource:
- `rag.feedback.created` → submitted
- Status update to `triaged` → triaged
- Status update to `resolved` → resolved
- Status update to `ignored` → ignored

The query is role-gated and tenant-scoped using the authenticated organization. It returns daily counts and period totals only; audit actor IDs, resource IDs, query digests, notes, and evidence IDs are not returned.

## Operator experience

The RAG Operator Workbench displays submission, triage, resolution, and ignored action totals, with a daily activity chart aligned to the existing 7/30/90-day selector.

## Interpretation and limitations

These values count audit actions, not unique feedback records. A single feedback item can be submitted, triaged, and later resolved or ignored, so summing lifecycle actions does not represent the number of distinct feedback items. Counts describe operator workflow activity; they are not measures of retrieval quality or correctness.

The endpoint reads the existing audit trail and adds no schema migration or new event writes.

## Validation

- OpenAPI route, bounded parameter, and authentication dependency checks.
- Tenant/resource/action filters on the audit aggregation query.
- Daily UTC aggregation, zero-filled dates, and empty-window tests.
- Full CI: Python checks, web production build, migrations, and container builds.

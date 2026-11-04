# Phase 85 — RAG feedback backlog aging

## Goal

Help operators prioritize unresolved user feedback by showing how long it has been waiting, without exposing individual feedback records or notes.

## API

`GET /api/v1/rag/operator/feedback/backlog` returns fixed UTC age buckets for feedback whose current status is `new` or `triaged`:

- Under 24 hours
- 1–7 days
- 7–30 days
- Over 30 days

The endpoint:
- Requires owner, admin, or instructor role.
- Derives organization scope from authenticated membership.
- Performs age classification and counts in the database.
- Returns zero-filled buckets, including statuses with no records.
- Excludes resolved and ignored feedback from the open backlog.
- Returns aggregate counts only; no query digest, note, actor ID, or evidence ID is exposed.

Age is calculated from each record's creation timestamp against the current UTC time. These are rolling age bands, not local-calendar-day counts.

## Operator experience

The RAG Operator Workbench displays total open feedback, new and triaged totals, and a table breaking each age band down by status. The view helps teams spot aging queues without implying that age itself measures retrieval quality.

## Interpretation and limitations

A backlog count is an operational workload signal, not a retrieval-quality metric. A high count may reflect participation volume, staffing, or triage practices. The endpoint does not expose or rank individual feedback entries.

## Validation

- OpenAPI route registration and authentication dependency contract.
- Tenant-scoped database query and open-status filter assertions.
- Correct age-bucket mapping and zero-filled bucket tests.
- Empty-queue behavior.
- Full CI: Python checks, web production build, migrations, and container builds.

No schema migration is required; the endpoint aggregates the existing feedback table.

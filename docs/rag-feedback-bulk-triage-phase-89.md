# Phase 89 — RAG feedback bulk triage

## Goal

Reduce repetitive operator work by allowing a small, selected set of feedback records to move through the existing triage state machine in one atomic operation.

## API

`POST /api/v1/rag/operator/feedback/bulk-update` accepts 1–50 unique feedback IDs and one target status (`triaged`, `resolved`, or `ignored`).

The endpoint:
- Requires owner, admin, or instructor role.
- Locks and loads every requested record within the active organization.
- Returns 404 if any requested record is missing or belongs to another organization.
- Validates every transition before mutating any row; one invalid transition rejects the whole batch with 409.
- Treats an item already at the target status as unchanged.
- Writes one existing `rag.feedback.status_updated` audit event for each changed record.
- Commits once for the complete batch and rolls back if an audit write or commit fails.

## Operator experience

The feedback queue provides checkboxes for new and triaged records, a target-status selector, and a bounded bulk action button. Selection is cleared when changing status filters or pages. Terminal statuses remain read-only.

## Validation

- Payload bounds and duplicate-ID rejection.
- Authentication and tenant scoping.
- Successful multi-item update and per-item audit writes.
- Atomic rejection when any transition is invalid.
- 404 behavior for missing or cross-tenant records.
- Full CI: Python checks, web production build, migrations, and container builds.

No schema migration is required. Existing single-item transitions remain available.

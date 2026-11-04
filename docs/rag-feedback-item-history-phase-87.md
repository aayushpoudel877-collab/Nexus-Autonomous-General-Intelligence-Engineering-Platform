# Phase 87 — RAG feedback item lifecycle history

## Goal

Let authorized operators inspect the lifecycle of an individual feedback record, while preserving tenant isolation and keeping audit actor details private.

## API

`GET /api/v1/rag/operator/feedback/{feedback_id}/history`:
- Requires owner, admin, or instructor role.
- First verifies that the feedback record belongs to the active organization; records from other organizations return 404.
- Reads only matching `rag_feedback` audit events for that organization and feedback resource.
- Returns the current status and an ascending timeline of submission, triage, resolution, and ignored timestamps.
- Omits actor identifiers and raw audit detail.

## Operator experience

The feedback queue now supports filters for new, triaged, resolved, and ignored records. Authorized operators can expand an item's lifecycle history and see its timestamps. Status controls reflect the existing forward-only transition rules: new items may be triaged, resolved, or ignored; triaged items may be resolved or ignored; terminal states have no further transition controls.

## Privacy and interpretation

The timeline is scoped to the active organization and exposes event labels and timestamps only. It does not expose audit actors, raw audit payloads, or other organizations' records. History may be empty for legacy records that predate lifecycle audit events.

## Validation

- OpenAPI route and authentication dependency checks.
- Tenant-scoped feedback existence lookup and 404 behavior.
- Tenant/resource/action filters on audit history.
- Ordered lifecycle event projection and exclusion of unknown status values.
- Full CI: Python checks, web production build, migrations, and container builds.

No schema migration or new audit event writes are introduced.

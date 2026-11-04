# Phase 90 — RAG bulk triage preview

## Goal

Give operators a non-mutating eligibility check before applying a selected batch of feedback status transitions.

## API

`POST /api/v1/rag/operator/feedback/bulk-preview` accepts the same bounded 1–50 unique feedback IDs and target status as the bulk-update endpoint.

The preview:
- Requires owner, admin, or instructor role.
- Loads only records belonging to the authenticated organization.
- Returns 404 if any requested record is missing or belongs to another organization.
- Counts eligible, unchanged, and blocked records, including blocked counts by current status.
- Returns `can_apply` only when no selected record has an invalid transition.
- Performs no writes, audit events, or commits.

The preview is informational, not a reservation. The bulk-update endpoint still locks records and revalidates every transition before applying changes, protecting against concurrent updates between preview and apply.

## Operator experience

The workbench adds a Preview selection action. It shows eligible, unchanged, and blocked counts and enables Apply only when the preview is eligible. Changing the selection, target status, filter, or page invalidates the previous preview.

## Validation

- Authentication and tenant-scope checks.
- Eligible, unchanged, and blocked transition counts.
- Missing/cross-tenant record behavior.
- No-mutation preview contract.
- Full CI: Python checks, web production build, migrations, and container builds.

No schema migration is required.

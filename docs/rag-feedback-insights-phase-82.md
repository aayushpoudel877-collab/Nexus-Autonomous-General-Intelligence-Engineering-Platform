# Phase 82 — Tenant-scoped RAG feedback insights

## Goal

Turn the existing RAG Studio usefulness ratings into actionable, privacy-conscious workspace signals for instructors and operators.

## API

- `GET /api/v1/rag/operator/feedback/summary` returns total feedback, helpful/unhelpful counts, lifecycle counts, and a helpful percentage.
- The endpoint is restricted to owner, admin, and instructor roles.
- Every aggregate is scoped to the authenticated membership's organization.
- The response contains aggregates only; it does not return raw queries, query digests, notes, actor identifiers, or evidence IDs.

## Operator experience

The RAG Operator Workbench now presents a feedback insight section alongside the existing retrieval diagnostics and triage queue. It shows response volume, helpful/unhelpful counts, helpful rate, and new/triaged/resolved/ignored totals. Existing triage actions remain unchanged.

## Privacy and interpretation

- A helpful rate is a descriptive signal, not a measure of factual correctness or semantic faithfulness.
- Small sample sizes can make percentages unstable; zero feedback is represented as a null rate, not 0%.
- Query digests and notes remain restricted to the existing triage workflow; the aggregate endpoint does not expose them.
- No raw query content is added to persistence.

## Acceptance

- OpenAPI registers the summary endpoint and existing route-authentication contract tests cover its authentication dependency.
- The complete CI workflow must pass, including Python checks, web production build, migrations, and containers.
- No migration is required because this phase aggregates existing feedback records.

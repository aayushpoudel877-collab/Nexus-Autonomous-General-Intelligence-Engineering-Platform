# RAG Phase 51 — Audited Retrieval Transaction Contracts

## Purpose

Strengthen the failure and persistence contracts around Phase 50's authenticated, tenant-scoped agentic retrieval endpoint.

## Implemented in this increment

- Verifies the endpoint uses the organization selected from authenticated membership rather than a request-supplied tenant.
- Verifies provenance is flushed and committed before a successful response is returned.
- Verifies raw query text is not included in the metadata-only audit event.
- Verifies retrieval/provenance failures return a fail-closed service error and roll back the request transaction.
- Verifies unexpected database commit failures trigger rollback rather than returning a successful response.

## Important test boundary

The new tests exercise API orchestration using a SQLAlchemy session double. They are transaction-contract tests, **not** PostgreSQL integration tests. The repository's PostgreSQL migration job validates schema upgrade/downgrade/re-upgrade, but it does not yet execute this endpoint against PostgreSQL.

## Acceptance still open

1. Add a PostgreSQL-backed endpoint test that creates isolated organization/user/membership records and verifies audit persistence and rollback against a real database.
2. Add human-reviewed, versioned prompt-injection cases across languages and attack families; current marker fixtures remain small and synthetic.
3. Run the full CI suite and review the resulting run before merging.

The marker detector remains diagnostic only. Retrieved content remains untrusted regardless of its marker score, and this phase does not enable model-generated plans or write-capable tools.

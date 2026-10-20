# Phase 53 — PostgreSQL idempotency and concurrency validation

## Why this phase exists

Phase 52 added request-ID replay handling and a PostgreSQL partial unique index, but the existing unit tests use session doubles. Those tests cannot prove that PostgreSQL enforces the uniqueness invariant under concurrent transactions.

## Changes

- Adds `tests/test_rag_phase53_postgres_idempotency.py`, which requires the migrated PostgreSQL database and skips locally when `DATABASE_URL` is not a PostgreSQL asyncpg URL.
- Verifies that an exact retry is a successful no-op and leaves exactly one audit row.
- Verifies that reusing a request ID with different sealed metadata fails closed and leaves the original row intact.
- Races two independent sessions with the same organization/request ID and asserts that PostgreSQL stores no more than one completion event.
- Adds the integration test to the existing PostgreSQL migration CI job after the clean schema upgrade.
- Updates the RAG roadmap to distinguish database-backed checks from unit/session-double contracts.

## Transaction and failure semantics

The audit writer intentionally flushes but does not commit. The calling API owns transaction boundaries. Concurrent duplicate writes may result in a uniqueness error for the losing transaction; callers must roll back and, where appropriate, read the committed row before deciding whether a retry succeeded. This phase tests the uniqueness invariant, not automatic retry recovery.

## Validation still required

- CI must pass on the branch, including the full test suite, migration downgrade/re-upgrade, and the PostgreSQL integration tests.
- Review actual CI logs before merging.
- Conduct a security review covering authenticated tenant scoping and human-reviewed multilingual prompt-injection cases.
- Add a true API-level PostgreSQL transaction test in a later increment; this phase directly tests the database-backed writer.

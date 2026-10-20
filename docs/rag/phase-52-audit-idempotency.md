# Phase 52 — Idempotent provenance audit retries

## Change

The database-backed RAG tool provenance writer now checks for a prior successful event matching the authenticated organization, action, and request ID. If the stored actor, resource type, resource ID, and sealed metadata all match, a retry is a no-op. Reusing the same request ID for different metadata or a different actor fails closed.

A PostgreSQL partial unique index on organization and request ID for rag.tool_execution.completed events closes the concurrent-insert race. The writer still flushes but never commits; the API retains ownership of the transaction.

## Privacy and security properties

- Raw tool output and individual evidence IDs remain excluded by the sealed metadata envelope.
- Request ID replay cannot silently overwrite an existing event.
- Cross-organization requests are rejected before the database lookup.
- Concurrent duplicate inserts are constrained by PostgreSQL; the losing insert fails closed and the caller must handle/retry only after checking the stored event.

## Validation still required

The new tests cover first write, exact replay, mismatched metadata, and actor mismatch with a session double. They are not PostgreSQL integration or concurrency tests. CI must pass, migrations must upgrade/downgrade/re-upgrade, and PostgreSQL-backed idempotency and concurrency tests plus security review remain open.

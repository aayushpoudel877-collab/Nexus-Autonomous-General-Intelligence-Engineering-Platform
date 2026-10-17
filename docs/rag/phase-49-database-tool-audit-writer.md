# Phase 49 — Database-Backed Tool Provenance Audit Writer

## Goal

Connect the Phase 48 execution-boundary writer contract to the repository's existing SQLAlchemy AuditEvent table without introducing a parallel audit store.

## Implemented

- Add a database writer factory bound to an organization UUID and optional authenticated actor/request identifiers.
- Compare the execution tenant identifier to the captured organization before any database operation.
- Verify the sealed Phase 47 envelope before persistence.
- Copy the envelope through deterministic JSON serialization to avoid retaining caller-owned nested references.
- Add a tenant-scoped AuditEvent with a fixed action/resource type and metadata-only details.
- Flush the event but never commit; the application retains ownership of transaction commit/rollback.
- Add unit tests for tenant isolation, invalid/tampered envelopes, identifier validation, safe payload storage, and end-to-end execution-wrapper integration.

## Storage and transaction semantics

This phase reuses the existing audit_events schema, so no schema migration is required. The audit event and any other work using the same AsyncSession can participate in the same caller-managed transaction. A successful flush is not a commit or a guarantee of durable storage; the caller must commit, and roll back if the operation fails.

The writer requires organization and actor context to be supplied by the authenticated application layer. It does not itself authenticate users or prove membership. Keep database sessions request-scoped and do not share them across concurrent tasks.

## Remaining acceptance work

- Wire the writer into the real authenticated API/request dependency that invokes agentic retrieval.
- Add database-backed integration tests against PostgreSQL for transaction rollback, tenant isolation, and retention.
- Confirm audit detail access controls and retention/deletion behavior with the platform audit policy.

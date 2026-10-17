# Phase 48 — Execution-Boundary Audit Persistence Hook

## Goal

Connect bounded read-only tool execution to the metadata-only provenance audit envelope so a caller cannot receive a successful audited result unless the supplied audit writer accepts the audit record.

## Implemented

- Add `execute_bounded_tool_plan_with_audit` as a wrapper around the existing allowlisted, scoped, budgeted tool executor.
- Require an explicit asynchronous audit writer and pass it only the tenant scope and sealed metadata-only envelope.
- Fail closed with a bounded execution error if the audit writer raises.
- Preserve existing tenant checks, tool scopes, argument validation, output limits, timeouts, and untrusted-output handling.
- Avoid writing provenance for an empty plan because no tool execution occurred.
- Add regression tests for safe metadata delivery, writer failure, missing writer, and empty plans.

## Contract and limitations

This is an execution-boundary adapter, not a built-in database implementation. The injected writer must derive/verify organization scope from authenticated request context, enforce authorization, and durably persist the envelope. A writer that merely returns without storing data does not provide durability. The wrapper cannot guarantee transaction atomicity across an external read-only tool and a separate audit store; the application must define retry/idempotency behavior and fail-closed response handling.

The checksum is not a signature. Store it in an appropriately protected audit system and use independent authorization, retention, and tenant isolation controls.

## Remaining acceptance work

- Implement a concrete writer against the repository's database-backed audit/event persistence layer.
- Verify tenant isolation and authorization in integration tests using authenticated request context.
- Add retry/idempotency and operational failure tests for storage outages.
- Review retention and deletion policy for the new audit detail payload.

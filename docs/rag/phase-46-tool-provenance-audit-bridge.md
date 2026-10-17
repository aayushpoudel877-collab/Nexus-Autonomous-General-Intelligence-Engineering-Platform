# Phase 46 — Tool Provenance Audit Bridge

## Goal

Provide a safe bridge from Phase 44 execution records and Phase 45 provenance validation into the existing privacy-safe RAG governance/audit contract.

## Implemented

- Add `build_tool_provenance_audit_details` to produce a versioned audit-detail envelope.
- Validate each record through the Phase 45 serializer before producing audit metadata.
- Preserve output digest, detector version, injection-marker categories, output character count, evidence count, tool identifier, and explicit untrusted status.
- Exclude raw output text and individual evidence IDs.
- Enforce the existing bounded provenance batch limit and reject altered output or trust-flag downgrades.
- Add regression tests for metadata-only serialization, tampering, batch bounds, and trust downgrade.

## Explicit non-goals and security boundaries

This is a serialization bridge, not a database write or an API route. It does not itself persist an audit event, authenticate a caller, select a tenant, or guarantee retention. Callers must use the existing authenticated organization context, transaction boundary, and audit persistence mechanism. Do not attach these details to lexical-only queries unless an actual tool execution occurred. SHA-256 checks integrity of the exact string supplied; it does not authenticate the source or establish factual safety.

## Next acceptance work

- Integrate at the actual agentic-tool execution boundary with organization-scoped actor/resource identifiers.
- Add database-backed integration tests proving audit details commit atomically with the corresponding operation.
- Confirm authorization, retention, and redaction behavior against the real audit API.
- Keep tool output out of audit detail payloads and add human-reviewed security cases.

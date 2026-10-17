# Phase 45 — Safe Tool Provenance Serialization

## Goal

Create a validated metadata-only projection of Phase 44 tool execution records so future API and audit integrations can preserve integrity and taint signals without copying raw tool output into logs or response metadata.

## Implemented

- Validate the tool identifier, detector version, marker categories, output length, evidence collection shape, and explicit untrusted status.
- Recompute SHA-256 over the exact UTF-8 output and reject a mismatched digest.
- Project only the digest, detector version, marker categories, character count, evidence count, tool name, and untrusted=true.
- Keep raw output text and individual evidence IDs out of the serialized provenance object.
- Bound each provenance batch to 12 records and preserve execution order.
- Add regression tests for privacy projection, digest mismatch, trust downgrade, invalid markers, length mismatch, and batch limits.

## Security boundaries

The digest is not source authentication and does not establish factual correctness or safety. Marker categories are heuristic diagnostics, not a blocker or authorization mechanism. Provenance records can still reveal tool names, counts, and behavioral metadata; callers must apply the application's authorization, retention, and access-control rules. This phase adds a serialization contract only: it does not claim that the current lexical /rag/query route invokes agentic tools or that metadata is already durably persisted by the API.

## Acceptance and follow-up

- Run Ruff, unit tests, and the existing RAG evaluation gates in CI.
- Integrate this projection only where tool execution actually occurs; do not fabricate tool metadata for lexical-only queries.
- Add authenticated API response and audit-storage integration tests before marking durable propagation complete.
- Review retention and redaction behavior with realistic, human-reviewed security cases.

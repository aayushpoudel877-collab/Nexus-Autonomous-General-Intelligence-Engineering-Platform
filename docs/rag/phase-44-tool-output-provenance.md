# RAG Phase 44 — Tool-Output Integrity Provenance

## Goal

Make each bounded retrieval-tool output easier to audit and reproduce without promoting untrusted content into instructions or claiming that a heuristic proves safety.

## Implemented foundation

Each `ToolExecutionRecord` now includes:

- `untrusted=true`, preserving the existing taint boundary.
- `content_sha256`, the SHA-256 digest of the exact UTF-8 output string before any downstream transformation.
- `detector_version`, the version identifier of the deterministic prompt-injection marker rules that produced `injection_markers`.
- Existing tool name, evidence IDs, output character count, and diagnostic marker categories.

The digest is stable for identical Unicode strings encoded as UTF-8. The detector version makes marker results interpretable when rule sets evolve. Tests assert that the digest matches the record's exact text and that the detector version matches the active rule implementation.

## Security and privacy boundaries

- A content digest is an integrity identifier, not proof of origin, authenticity, truth, or safety.
- Marker detection is a heuristic. An empty marker list does not mean an output is safe; a flagged output is not automatically malicious.
- Tool output remains untrusted even when its digest is present or no markers fire.
- Do not log raw output merely to make digesting possible; the digest is calculated in memory and does not require durable raw-text storage.
- Tool authorization, strict argument schemas, tenant checks, read-only tool policy, timeout limits, and output budgets remain independent controls.

## Validation

The focused agentic retrieval tests verify that execution records retain untrusted tagging and marker behavior while including a 64-character SHA-256 digest and the active detector version.

The repository's full test suite, lint, database migration checks, web build, and container builds must still run in CI against the exact commit before this phase is treated as release-ready.

## Remaining acceptance

- Propagate trust metadata through API response contracts and durable audit records without leaking unnecessary raw content.
- Add integration tests showing that untrusted result text cannot modify authorization, tenant selection, tool registry, or execution policy.
- Add reviewed multilingual and Unicode-obfuscation evaluation examples.
- Define retention and access controls for provenance metadata in persistent audit storage.
- Keep any model-backed planner disconnected until policy review and end-to-end authorization tests are complete.

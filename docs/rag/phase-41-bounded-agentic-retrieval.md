# RAG Phase 41 — Bounded Agentic Retrieval

## Implemented foundation

This phase adds a sequential tool-plan executor that only calls tools explicitly supplied in a registry.

- Per-tool scope requirements, call limits, timeout, output limits, and read-only declaration.
- Request-level step, aggregate output-character, and unique evidence-ID budgets.
- Tenant ID is passed to every tool and the result tenant must match exactly.
- Strict JSON-compatible argument validation, nesting/size limits, and rejection of credential-like argument keys.
- Tool exceptions are returned as generic execution errors so provider/tool internals are not copied into user-facing error messages.
- Tool output is represented as untrusted data with evidence IDs, not promoted to instructions.
- Async tests cover allowlisting, scope checks, cross-tenant results, call/step/output budgets, timeout, and argument validation.

## Security boundary

This module does not discover tools, invoke shell commands, make network requests, or grant permissions. Callers must register only read-only retrieval adapters and must implement authorization and input validation inside each adapter as well. The `read_only` declaration is a contract assertion, not a sandbox; it cannot prove that a caller-provided function has no side effects.

This is not a complete autonomous agent or a production deployment of external tools. The executor is sequential, and it does not provide durable orchestration, retries, rollback, or distributed rate limiting.

## Remaining acceptance

- Add typed, per-tool argument schemas instead of relying only on generic JSON validation.
- Integrate only a small set of read-only retrieval tools with tenant-scoped database queries.
- Add database-backed integration tests for authorization and cross-tenant leakage.
- Add persistent run/audit records, cancellation handling, and operational metrics.
- Threat-model each adapter before adding external services or write-capable actions.

# RAG Phase 43 — Untrusted Tool Output Handling

## Implemented foundation

The bounded tool executor now attaches prompt-injection marker metadata to each result while preserving the rule that all tool output is untrusted data.

- Each execution record includes `untrusted=true`.
- The existing deterministic marker baseline labels suspicious instruction override, prompt/secret disclosure, tool misuse, safety bypass, and external exfiltration patterns.
- Markers are diagnostic metadata only; they do not silently remove or block retrieved evidence.
- Tests demonstrate both a clear instruction-override marker and a benign training sentence that is flagged as a likely false positive.

## Security boundary

Marker detection is incomplete and language-dependent. An empty marker list does not mean content is safe, and a non-empty list does not prove an attack. The labels must not be used as authorization. Tool allowlists, strict argument schemas, tenant checks, output limits, and separate execution boundaries remain mandatory.

This phase does not connect a model planner to the tool executor. Tool plans remain caller-supplied, bounded, and sequential.

## Remaining acceptance

- Add reviewed multilingual indirect-injection cases and Unicode-confusable/obfuscated examples.
- Carry taint metadata through API responses and durable audit records without storing unnecessary raw content.
- Add integration tests showing untrusted evidence cannot alter tool permissions or tenant scope.
- Require explicit policy review before any model-backed planner or write-capable tool is introduced.

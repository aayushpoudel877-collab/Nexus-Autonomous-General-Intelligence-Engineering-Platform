# RAG Phase 42 — Tool Planning Evaluation

## Implemented foundation

This phase adds typed tool argument contracts and a reproducible offline evaluation of proposed retrieval tool selections.

- Every registered retrieval tool must declare a Pydantic argument model with extra fields forbidden.
- Generic JSON bounds and credential-like key rejection run before the tool-specific schema.
- Tool argument schema failures are converted into a policy error without exposing detailed validation payloads.
- A bounded JSONL evaluator reports tool-selection precision/recall/F1, missing and extra selections, forbidden tool attempts, and language/risk slices.
- CI runs the evaluator and archives its deterministic JSON report.
- Synthetic fixtures include a disallowed shell proposal, a multilingual missed case, an over-selection, and a no-tool-needed case.

## Security boundary

The selection evaluator scores recorded proposals; it does not call a language model or establish semantic safety. The committed examples are synthetic contract fixtures, not a human-reviewed benchmark. An expected tool must always be within the case's allowed set, and disallowed proposed tools count as policy violations.

Tool schemas constrain arguments but do not sandbox the executor. Each registered adapter must still enforce tenant ownership, authorization, output bounds, and side-effect policy.

## Remaining acceptance

- Replace synthetic cases with human-reviewed tool-selection and prompt-injection scenarios.
- Measure selection quality and forbidden-tool attempt rates by risk category and language.
- Add property-based tests for malformed argument structures and schema edge cases.
- Test each real adapter against database-backed tenant isolation and authorization cases.
- Use a model-backed planner only after the evaluation gate and audit controls are in place.

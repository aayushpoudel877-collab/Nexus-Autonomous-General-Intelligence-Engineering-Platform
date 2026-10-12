# Phase 32 — Provider-neutral generation adapters

## Scope

This phase adds a model-provider contract and a bounded orchestration layer for evidence-grounded answers. It deliberately does not add provider credentials or bind the platform to one hosted API. A concrete local or hosted adapter implements `GenerationProvider` and returns `ProviderGeneration`.

## Contract

- `GenerationRequest`: question, uniquely identified evidence, prompt version, and explicit input/output/context/answer/time/attempt limits.
- `GenerationProvider`: asynchronous `generate` contract with system/user prompts and a hard output-token request.
- `ProviderGeneration`: provider output and optional token usage/model metadata.
- `GenerationAnswer`: validated answer, evidence IDs, abstention flag, prompt version, model identifier, attempts and usage.
- `generate_grounded_answer`: builds a versioned evidence prompt, enforces a conservative preflight input estimate, applies an asynchronous timeout, bounds retries to three attempts, validates reported usage, parses a strict JSON response and rejects unknown or duplicate citations.

## Safety behavior

- Evidence is explicitly labeled untrusted data in the system prompt. Instructions embedded in retrieved documents must not be followed.
- A non-abstaining response must contain non-empty answer text and at least one citation that matches supplied evidence.
- Unknown evidence IDs, duplicate citations, malformed JSON, invalid schemas and oversized outputs fail closed.
- Empty evidence returns a canonical abstention without making a provider call. Provider-declared abstention is normalized to the same canonical message.
- Only timeouts and explicitly classified `TransientGenerationError` failures are retried. Invalid output is not silently accepted or retried indefinitely.
- Provider-reported token usage is checked against configured limits. The provider adapter must also enforce its own account/project spending limits; this layer does not claim exact dollar-cost accounting.

## Example

```python
answer = await generate_grounded_answer(
    provider,
    GenerationRequest(
        question="What is the documented policy?",
        evidence=(GenerationEvidence("E1", "The policy states ...", "Policy"),),
        max_input_tokens=8_000,
        max_output_tokens=800,
        timeout_seconds=20,
        max_attempts=2,
    ),
)
if answer.abstained:
    # Show the canonical abstention to the caller.
    ...
else:
    # Render answer.answer and its answer.citations as source links.
    ...
```

## Validation

Unit tests cover grounded answers, canonical abstention, malformed/untrusted citations, duplicate citations, strict output schema, prompt and usage budgets, output limits, transient retry bounds, timeouts, and request validation.

## Explicitly not claimed

No live provider SDK, API endpoint, streaming output, persistent conversation history, exact financial cost ledger, independent claim-entailment verification, or measured production answer quality is implemented in this phase. The orchestration layer validates citation identifiers, but a future grounding phase must verify that cited passages actually support individual claims.

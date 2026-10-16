# RAG Phase 40 — Prompt-Injection Evaluation Baseline

## Implemented foundation

The existing generation prompt treats retrieved passages as untrusted data. This phase adds a deterministic, offline evaluation baseline for suspicious instruction markers found in retrieved text.

- Bounded text length and case count, with unique case IDs.
- Explainable marker categories for instruction override, prompt/secret disclosure, tool misuse, safety bypass, and external exfiltration.
- Aggregate precision, recall, F1, confusion counts, and explicit false-positive/false-negative IDs.
- Metrics sliced by language and risk category.
- Tests include a deliberately missed Nepali example and a benign example that triggers a marker, making the detector's limitations visible.

## Security boundary

The detector is a lexical heuristic, not a semantic classifier. It can miss paraphrases, non-English attacks, obfuscation, or context-dependent attacks, and it can flag benign discussion of attack techniques. It must not be used as a standalone security boundary or as an automatic reason to discard evidence. Its output is intended for offline evaluation and for measuring rule changes against reviewed labels.

Retrieved text remains untrusted regardless of the detector result. Tool execution, secrets access, network egress, authorization, and tenant isolation must be controlled by separate policy and runtime boundaries.

## Remaining acceptance

- Build a human-reviewed, versioned prompt-injection corpus across languages and modalities.
- Measure precision/recall by attack family and language, and compare rule versions with regression thresholds.
- Add obfuscation, indirect prompt injection, Unicode confusables, encoded payloads, and benign quoted examples.
- Add model-assisted red-team evaluation only with bounded cost, privacy controls, and human review.
- Implement agentic retrieval separately with explicit tool allowlists, per-tool authorization, budgets, and audit trails.

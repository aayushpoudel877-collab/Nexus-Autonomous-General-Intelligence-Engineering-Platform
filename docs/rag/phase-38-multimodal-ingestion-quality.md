# RAG Phase 38 — Multimodal Ingestion Quality

## Implemented hardening

The current multimodal index stores bounded text representations, not raw image/audio/video bytes. This increment hardens metadata filtering and provenance identifiers:

- Credential-like metadata keys are rejected across common separator/case variants, including API-key, bearer, session, private-key, and authorization patterns.
- Representation chunk IDs percent-encode asset and representation identifiers before combining them, preventing collisions caused by identifiers containing the delimiter.
- Existing tenant ownership, modality/kind compatibility, text/metadata limits, timestamp/page validation, and provenance fields remain enforced.
- Regression tests cover secret-key aliases, a non-sensitive author field, and previously colliding asset/representation pairs.

## Explicit boundary

This does not implement OCR, speech-to-text, video frame extraction, raw media decoding, durable vector indexing, or external media-provider calls. It indexes bounded text produced by a separately controlled extraction pipeline. Captions, OCR output, transcripts, and metadata must be treated as untrusted input, not instructions.

## Remaining acceptance

- Add provider adapters behind explicit byte, duration, timeout, cost, and output-size budgets.
- Test malformed media, decompression bombs, parser timeouts, cancellation, and quarantine flows.
- Add reviewed image/audio/video relevance cases and modality-specific quality metrics.
- Integrate durable vector persistence and verify deletion/retention behavior across all representations.

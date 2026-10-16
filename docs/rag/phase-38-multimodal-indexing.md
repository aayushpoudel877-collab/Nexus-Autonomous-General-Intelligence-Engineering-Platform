# RAG Phase 38 — Multimodal Indexing Foundation

## Objective

Represent extracted text from images, audio, video, and structured assets as ordinary tenant-scoped retrieval chunks while preserving enough provenance to trace each result back to its source representation.

## Delivered in this phase

- A provider-neutral, validated representation contract for captions, OCR, transcripts, extracted text, and metadata.
- Explicit modality-to-representation compatibility rules.
- Bounded text and metadata sizes; rejects credential-like metadata keys and duplicate metadata names.
- Audio/video timestamp validation and page provenance validation.
- Conversion to the existing `Chunk` contract, preserving tenant ID, asset ID, stable representation-aware chunk IDs, ordinals, and character offsets.
- Unit tests for valid indexing, provenance, invalid modality combinations, limits, and chunk identity collisions.

## Security and correctness boundaries

- This phase accepts text representations only; it does not read arbitrary media bytes or fetch source URIs.
- OCR, captioning, transcription, media parsing, embedding generation, and durable vector storage are not implemented by this contract.
- Callers must obtain extracted text through a trusted, separately secured pipeline and must not treat media-derived instructions as trusted system instructions.
- Tenant scoping is carried into every output chunk. A future persistent index must also enforce tenant filters at the storage query boundary.
- Chunk offsets refer to the representation text, not the original binary asset.

## Acceptance checklist

- [x] Contract validates modality-specific provenance.
- [x] Text representations are bounded before chunking.
- [x] Output reuses the existing retrieval chunk contract.
- [x] Regression tests cover provenance and stable IDs.
- [ ] Full CI and security review pass before merge.
- [ ] Provider-backed OCR/transcription and durable indexing remain later phases.

# RAG Phase 38 — Multimodal Retrieval Quality Evaluation

## Implemented increment

The existing multimodal index converts controlled extraction outputs (captions, OCR text, transcripts, and extracted metadata) into bounded tenant-scoped text representations. This increment adds an offline evaluation path that reports retrieval quality separately for `text`, `image`, `audio`, `video`, and `structured` queries.

- Strict JSONL modality-map loader with size limits inherited from the shared evaluation reader, duplicate rejection, and supported-modality validation.
- Per-run aggregate metrics plus modality-specific precision@k, recall@k, reciprocal rank, NDCG@k, and empty-result rate.
- Missing predictions count as empty results; unknown cases, duplicate run/case predictions, and incomplete modality mappings fail closed.
- Reports explicitly state that retrieval relevance metrics do not measure OCR/transcription fidelity and synthetic fixtures are not production evidence.

## Usage

Create a JSONL modality map with exactly `case_id` and `modality` per line, where modality is one of the supported values. Use the evaluation API:

```python
from services.rag.evaluation import load_golden_dataset, load_predictions
from services.rag.multimodal_evaluation import load_modality_map, evaluate_multimodal_slices

cases = load_golden_dataset("path/to/golden.jsonl")
predictions = load_predictions("path/to/predictions.jsonl")
modalities = load_modality_map("path/to/modalities.jsonl")
report = evaluate_multimodal_slices(cases, predictions, modalities, k=5)
```

## Explicit boundary

This is an offline evaluator; it does not decode raw media or call OCR/speech/video providers. It does not claim that an image, audio, or video extraction is correct. Captions, OCR output, transcripts, and metadata remain untrusted input, not instructions.

## Remaining acceptance

- Add human-reviewed image/audio/video relevance cases and modality-specific quality labels.
- Add extraction fidelity metrics for OCR/transcription only when reference transcripts or annotations are available.
- Test malformed media, decompression bombs, parser timeouts, cancellation, and quarantine flows.
- Integrate durable vector persistence and verify deletion/retention behavior across all representations.

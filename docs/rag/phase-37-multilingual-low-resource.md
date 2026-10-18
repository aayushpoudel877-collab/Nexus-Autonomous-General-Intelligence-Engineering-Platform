# RAG Phase 37 — Multilingual and Low-Resource Retrieval

## Implemented foundation

The existing Unicode-aware tokenizer supports scripts beyond Latin, and optional character n-gram coverage can assist retrieval when whitespace does not reliably separate words. The n-gram weight remains opt-in and defaults to zero.

This increment adds a deterministic, dependency-free paired bootstrap evaluation report:

- Per-language precision@k, recall@k, reciprocal rank, NDCG@k, and empty-result rate.
- Percentile confidence intervals for baseline and candidate runs.
- Paired candidate-minus-baseline intervals computed by resampling the same cases for both runs.
- Bounded bootstrap sample counts, reproducible seeds, strict duplicate/unknown case checks, and explicit reporting limitations.

Run the evaluation from Python after producing ranked predictions for both runs:

```python
from services.rag.evaluation import load_golden_dataset, load_predictions
from services.rag.multilingual_evaluation import build_multilingual_ablation_report

cases = load_golden_dataset("tests/fixtures/rag/golden.jsonl")
predictions = load_predictions("tests/fixtures/rag/predictions.jsonl")
report = build_multilingual_ablation_report(
    cases, predictions, baseline_name="baseline", candidate_name="ngram-04",
    k=5, bootstrap_samples=1000, seed=37,
)
```

## Limits and safety

Character n-grams are a lexical matching signal, not semantic search, translation, language identification, stemming, or proof of relevance. They can increase false positives for short or common substrings. Tenant filtering must occur before scoring.

Confidence intervals quantify resampling variability in the supplied sample; they do not guarantee population-wide performance. The repository's synthetic fixtures are contract tests, not a human-reviewed multilingual benchmark. Do not claim production effectiveness until reviewers have assembled representative relevance labels for Nepali and other low-resource languages.

## Remaining acceptance work

- Build and review a multilingual query/relevance dataset with native or qualified language reviewers.
- Run baseline BM25 versus several n-gram weights and report per-language intervals from reviewed predictions.
- Evaluate spelling variants, transliteration, code-switching, morphology, and adversarially similar strings.
- Add language detection or language-specific segmentation only when measured evidence supports the dependency and operational cost.

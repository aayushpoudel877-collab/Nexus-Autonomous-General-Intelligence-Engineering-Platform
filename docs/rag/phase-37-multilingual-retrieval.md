# RAG Phase 37 — Multilingual and Low-Resource Retrieval Foundation

## Objective

Make the deterministic lexical baseline usable for languages and scripts beyond Latin, without claiming that tokenization alone solves multilingual retrieval.

## Delivered in this phase

- Unicode NFC normalization before tokenization.
- Unicode-aware extraction of letters, numbers, and combining marks.
- Unicode case-folding rather than ASCII-only lowercasing.
- Regression tests for Nepali/Devanagari, Arabic, Cyrillic, Japanese, Latin diacritics, punctuation, and invalid input.
- Existing BM25 ranking now consumes the multilingual tokens through the shared `tokenize` function; tenant scoping and document filters are unchanged.

## Known limits

- No stemming, lemmatization, translation, transliteration, or language detection.
- No dictionary-based segmentation for languages without whitespace-delimited words; CJK text is currently split into contiguous letter/number runs, not semantically segmented terms.
- Unicode-aware matching improves script coverage but does not demonstrate retrieval quality. Quality claims require human-reviewed multilingual relevance judgments and per-language evaluation.
- Existing synthetic evaluation fixtures are contract tests, not evidence of production effectiveness.

## Acceptance checklist

- [x] Unicode-aware tokenizer with no new runtime dependency.
- [x] Regression tests for representative scripts and decomposed accents.
- [x] Existing ranking path reuses the tokenizer.
- [ ] Run complete Python suite, lint, web build, and migration CI.
- [ ] Add a human-reviewed multilingual golden set before making quality claims.
- [ ] Evaluate per-language recall@k, MRR, and NDCG before production rollout.

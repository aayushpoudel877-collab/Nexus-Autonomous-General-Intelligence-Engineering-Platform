# RAG Phase 37 — Multilingual and Low-Resource Retrieval

## Implemented foundation

The existing Unicode-aware tokenizer continues to support word-boundary lexical matching. This phase adds an optional character n-gram coverage score for scripts and text where whitespace does not reliably separate words.

- Character n-grams are generated from Unicode letter/number runs after NFKC normalization and case folding.
- Query coverage is measured as the fraction of query n-grams present in a candidate chunk.
- The retrieval library accepts `character_ngram_weight` from 0 through 1. A value of 0 is the default and preserves the prior ranking behavior; larger values blend the character n-gram score with the existing lexical/dense score.
- The authenticated RAG query API validates the weight as finite and bounded.
- The operator workbench exposes the setting for retrieval diagnostics.
- Regression tests cover Japanese text without spaces, Devanagari text, short strings, invalid weights, default behavior, and tenant scoping.

## Limits and safety

Character n-grams are a lexical matching signal, not semantic search, translation, language identification, stemming, or proof of relevance. They can increase false positives for short or common substrings. The weight should be tuned against reviewed queries and per-language metrics before production use. Existing tenant filtering remains in place before scoring.

## Acceptance still open

- Build a human-reviewed multilingual query/relevance dataset that includes Nepali and other low-resource languages.
- Report precision@k, recall@k, MRR, NDCG, empty-result rate, and confidence intervals per language and script.
- Compare baseline BM25 against character n-gram blends with ablation runs and a documented regression threshold.
- Evaluate spelling variants, transliteration, code-switching, morphology, and adversarially similar strings.
- Add language detection and language-specific segmentation only when measured evidence supports the dependency and operational cost.

The current automated fixtures are synthetic contract tests; they do not establish production retrieval quality.

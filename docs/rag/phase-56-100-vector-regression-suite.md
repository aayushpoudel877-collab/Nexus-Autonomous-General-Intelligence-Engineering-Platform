# Phase 56 — 100-vector RAG integrity regression suite

This phase adds a data-driven regression corpus for the source-integrity primitive. Each vector is independently committed so a reviewer can trace and revert a specific case without rewriting the entire corpus.

## Coverage

- Stable SHA-256 verification for unchanged content
- Mutated content and digest mismatch reporting
- Missing source bytes and unavailable status
- Per-call size-limit behavior
- Multilingual text including Nepali, Arabic, Japanese, and accented Latin text
- Newlines, tabs, escaped characters, JSON/XML/CSV/SQL-like text, code, Markdown, punctuation, and combining Unicode characters

The 100 JSON fixtures are exercised by `tests/test_rag_integrity_fixture_vectors.py`. The test asserts the full corpus count, expected status, and reason code for every vector.

## Run locally

```bash
pytest tests/test_rag_source_integrity.py tests/test_rag_integrity_fixture_vectors.py
```

## Commit discipline

The corpus contains 100 isolated fixture commits plus the regression harness commit in this phase branch. These are not empty commits: each adds a distinct named input/expected-result vector to the automated test corpus. The earlier Phase 55 persistent worker and persistence normalization changes are ancestors of this branch and are not counted in the 100 fixture commits.

## Limits

These fixtures validate the byte-digest primitive, not the entire database-backed worker, tenant authorization, scheduler, vector-store state, or production deployment. Those need integration tests against the repository's configured database and deployment environment.

"""Transparent hybrid retrieval and evidence packing without model/provider coupling."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
import math
import unicodedata

from .chunking import Chunk

def character_ngrams(text: str, *, min_n: int = 2, max_n: int = 4) -> set[str]:
    """Return deterministic character n-grams within Unicode letter/number runs.

    This is an optional lexical fallback for scripts and languages where whitespace
    tokenization does not separate words. It is not translation, stemming, or semantic
    matching. Short runs are retained as whole units so single-character queries work.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not 1 <= min_n <= max_n <= 8:
        raise ValueError("n-gram bounds must satisfy 1 <= min_n <= max_n <= 8")
    normalized = unicodedata.normalize("NFKC", text).casefold()
    runs: list[str] = []
    current: list[str] = []
    for character in normalized:
        category = unicodedata.category(character)
        if category[0] in {"L", "N"} or (category[0] == "M" and current):
            current.append(character)
        elif current:
            runs.append("".join(current))
            current = []
    if current:
        runs.append("".join(current))

    grams: set[str] = set()
    for run in runs:
        if len(run) < min_n:
            grams.add(run)
            continue
        for size in range(min_n, min(max_n, len(run)) + 1):
            grams.update(run[index : index + size] for index in range(len(run) - size + 1))
    return grams


def character_ngram_similarity(query: str, text: str, *, min_n: int = 2, max_n: int = 4) -> float:
    """Return query-gram coverage in a candidate text, in [0, 1]."""
    query_grams = character_ngrams(query, min_n=min_n, max_n=max_n)
    if not query_grams:
        return 0.0
    text_grams = character_ngrams(text, min_n=min_n, max_n=max_n)
    return len(query_grams & text_grams) / len(query_grams)


def tokenize(text: str) -> list[str]:
    """Tokenize Unicode text while preserving letters, digits, and combining marks.

    This deterministic baseline supports scripts beyond Latin without a language
    detector or external dependency. It does not perform stemming, translation,
    or word segmentation for scripts that do not use whitespace.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    normalized = unicodedata.normalize("NFC", text)
    tokens: list[str] = []
    current: list[str] = []
    for character in normalized:
        category = unicodedata.category(character)
        if category[0] in {"L", "N"} or character == "_" or (category[0] == "M" and current):
            current.append(character)
        elif current:
            tokens.append("".join(current).casefold())
            current = []
    if current:
        tokens.append("".join(current).casefold())
    return tokens


@dataclass(frozen=True)
class RetrievalHit:
    chunk: Chunk
    lexical_score: float
    dense_score: float
    fused_score: float
    character_ngram_score: float = 0.0


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    document_id: str
    chunk_id: str
    title: str
    text: str
    source_uri: str
    start_char: int
    end_char: int
    score: float
    character_ngram_score: float = 0.0


def _lexical_scores(
    query: str,
    chunks: list[Chunk],
    *,
    k1: float = 1.2,
    b: float = 0.75,
) -> dict[str, float]:
    """Compute normalized BM25 scores with explicit, validated tuning parameters."""
    if not math.isfinite(k1) or k1 <= 0:
        raise ValueError("BM25 k1 must be finite and positive")
    if not math.isfinite(b) or not 0 <= b <= 1:
        raise ValueError("BM25 b must be between 0 and 1")
    query_terms = set(tokenize(query))
    if not query_terms or not chunks:
        return {}
    documents = [Counter(tokenize(chunk.text)) for chunk in chunks]
    lengths = [sum(counts.values()) for counts in documents]
    average_length = sum(lengths) / max(1, len(lengths))
    document_frequency = {
        term: sum(term in counts for counts in documents) for term in query_terms
    }
    scores: dict[str, float] = {}
    for chunk, counts, length in zip(chunks, documents, lengths):
        score = 0.0
        for term in query_terms:
            frequency = counts[term]
            if not frequency:
                continue
            inverse_frequency = math.log(
                1 + (len(chunks) - document_frequency[term] + 0.5)
                / (document_frequency[term] + 0.5)
            )
            normalization = k1 * (1 - b + b * length / max(average_length, 1))
            score += inverse_frequency * (
                frequency * (k1 + 1) / (frequency + normalization)
            )
        scores[chunk.chunk_id] = score
    maximum = max(scores.values(), default=0.0)
    return {key: value / maximum for key, value in scores.items()} if maximum else scores


def hybrid_retrieve(
    query: str,
    chunks: Iterable[Chunk],
    *,
    tenant_id: str,
    top_k: int = 5,
    dense_scores: dict[str, float] | None = None,
    lexical_weight: float = 0.65,
    character_ngram_weight: float = 0.0,
    bm25_k1: float = 1.2,
    bm25_b: float = 0.75,
    allowed_document_ids: set[str] | None = None,
    excluded_document_ids: set[str] | None = None,
    per_document_limit: int | None = None,
) -> list[RetrievalHit]:
    """Retrieve tenant-scoped chunks with tunable BM25/dense fusion and filters.

    Dense scores are trusted adapter outputs keyed by chunk ID and must be in [-1, 1].
    Document allow/deny filters are applied after tenant scoping. Per-document
    diversification is applied after deterministic score sorting.
    """
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("tenant_id is required")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query is required")
    if not 1 <= top_k <= 100 or not 0 <= lexical_weight <= 1:
        raise ValueError("invalid top_k or lexical_weight")
    if not math.isfinite(character_ngram_weight) or not 0 <= character_ngram_weight <= 1:
        raise ValueError("character_ngram_weight must be finite and between 0 and 1")
    if per_document_limit is not None and per_document_limit < 1:
        raise ValueError("per_document_limit must be positive")
    if not math.isfinite(lexical_weight):
        raise ValueError("lexical_weight must be finite")
    scoped = [chunk for chunk in chunks if chunk.tenant_id == tenant_id]
    if allowed_document_ids is not None:
        scoped = [chunk for chunk in scoped if chunk.document_id in allowed_document_ids]
    excluded = excluded_document_ids or set()
    scoped = [chunk for chunk in scoped if chunk.document_id not in excluded]
    dense_scores = dense_scores or {}
    if any(not math.isfinite(score) or not -1 <= score <= 1 for score in dense_scores.values()):
        raise ValueError("dense similarity must be finite and between -1 and 1")
    lexical = _lexical_scores(query, scoped, k1=bm25_k1, b=bm25_b)
    hits: list[RetrievalHit] = []
    for chunk in scoped:
        lexical_score = lexical.get(chunk.chunk_id, 0.0)
        dense_score = (
            (dense_scores[chunk.chunk_id] + 1.0) / 2.0
            if chunk.chunk_id in dense_scores
            else 0.0
        )
        base_score = lexical_weight * lexical_score + (1 - lexical_weight) * dense_score
        ngram_score = (
            character_ngram_similarity(query, chunk.text)
            if character_ngram_weight > 0
            else 0.0
        )
        fused_score = (
            (1 - character_ngram_weight) * base_score
            + character_ngram_weight * ngram_score
        )
        if lexical_score > 0 or chunk.chunk_id in dense_scores or ngram_score > 0:
            hits.append(
                RetrievalHit(chunk, lexical_score, dense_score, fused_score, ngram_score)
            )
    hits.sort(key=lambda hit: (-hit.fused_score, hit.chunk.document_id, hit.chunk.ordinal))
    if per_document_limit is None:
        return hits[:top_k]
    selected: list[RetrievalHit] = []
    counts: dict[str, int] = {}
    for hit in hits:
        document_id = hit.chunk.document_id
        if counts.get(document_id, 0) >= per_document_limit:
            continue
        counts[document_id] = counts.get(document_id, 0) + 1
        selected.append(hit)
        if len(selected) >= top_k:
            break
    return selected


def pack_evidence(
    hits: Iterable[RetrievalHit],
    document_titles: dict[str, str] | None = None,
    source_uris: dict[str, str] | None = None,
) -> list[Evidence]:
    """Package ranked hits as stable, unique evidence references."""
    titles, uris = document_titles or {}, source_uris or {}
    evidence: list[Evidence] = []
    seen: set[str] = set()
    for hit in hits:
        if hit.chunk.chunk_id in seen:
            continue
        seen.add(hit.chunk.chunk_id)
        evidence.append(
            Evidence(
                f"E{len(evidence) + 1}",
                hit.chunk.document_id,
                hit.chunk.chunk_id,
                titles.get(hit.chunk.document_id, hit.chunk.document_id),
                hit.chunk.text,
                uris.get(hit.chunk.document_id, ""),
                hit.chunk.start_char,
                hit.chunk.end_char,
                hit.fused_score,
                hit.character_ngram_score,
            )
        )
    return evidence

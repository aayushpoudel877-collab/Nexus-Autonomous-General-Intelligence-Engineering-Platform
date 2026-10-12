"""Transparent hybrid retrieval and evidence packing without model/provider coupling."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
import math
import re

from .chunking import Chunk

_TOKEN = re.compile(r"[a-z0-9_]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    """Return lowercase alphanumeric tokens for the baseline lexical ranker."""
    return [token.lower() for token in _TOKEN.findall(text)]


@dataclass(frozen=True)
class RetrievalHit:
    chunk: Chunk
    lexical_score: float
    dense_score: float
    fused_score: float


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
        fused_score = lexical_weight * lexical_score + (1 - lexical_weight) * dense_score
        if lexical_score > 0 or chunk.chunk_id in dense_scores:
            hits.append(RetrievalHit(chunk, lexical_score, dense_score, fused_score))
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
            )
        )
    return evidence

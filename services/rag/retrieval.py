"""Transparent hybrid retrieval and evidence packing without model/provider coupling."""
from __future__ import annotations
from dataclasses import dataclass
import math
import re
from collections import Counter, defaultdict
from typing import Iterable
from .chunking import Chunk

_TOKEN = re.compile(r"[a-z0-9_]+", re.I)
def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]

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

def _lexical_scores(query: str, chunks: list[Chunk]) -> dict[str, float]:
    qterms = set(tokenize(query))
    if not qterms or not chunks:
        return {}
    docs = [Counter(tokenize(c.text)) for c in chunks]
    avg_len = sum(sum(d.values()) for d in docs) / max(1, len(docs))
    df = {term: sum(term in d for d in docs) for term in qterms}
    scores: dict[str, float] = {}
    for chunk, counts in zip(chunks, docs):
        length = sum(counts.values())
        score = 0.0
        for term in qterms:
            tf = counts[term]
            if not tf:
                continue
            idf = math.log(1 + (len(chunks) - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * length / max(avg_len, 1)))
        scores[chunk.chunk_id] = score
    maximum = max(scores.values(), default=0.0)
    return {key: value / maximum for key, value in scores.items()} if maximum else scores

def hybrid_retrieve(query: str, chunks: Iterable[Chunk], *, tenant_id: str, top_k: int = 5, dense_scores: dict[str, float] | None = None, lexical_weight: float = 0.65) -> list[RetrievalHit]:
    """Retrieve only tenant-matching chunks and fuse normalized lexical/dense scores.

    dense_scores are caller-provided similarity values keyed by chunk_id and must be
    produced by a trusted adapter. Values outside [-1, 1] are rejected.
    """
    if not tenant_id.strip() or not query.strip():
        raise ValueError("tenant_id and query are required")
    if not 1 <= top_k <= 100 or not 0 <= lexical_weight <= 1:
        raise ValueError("invalid top_k or lexical_weight")
    scoped = [c for c in chunks if c.tenant_id == tenant_id]
    dense_scores = dense_scores or {}
    if any(not -1 <= v <= 1 for v in dense_scores.values()):
        raise ValueError("dense similarity must be between -1 and 1")
    lexical = _lexical_scores(query, scoped)
    hits = []
    for chunk in scoped:
        ls = lexical.get(chunk.chunk_id, 0.0)
        ds = (dense_scores.get(chunk.chunk_id, -1.0) + 1.0) / 2.0 if chunk.chunk_id in dense_scores else 0.0
        fused = lexical_weight * ls + (1 - lexical_weight) * ds
        if ls > 0 or chunk.chunk_id in dense_scores:
            hits.append(RetrievalHit(chunk, ls, ds, fused))
    hits.sort(key=lambda h: (-h.fused_score, h.chunk.document_id, h.chunk.ordinal))
    return hits[:top_k]

def pack_evidence(hits: Iterable[RetrievalHit], document_titles: dict[str, str] | None = None, source_uris: dict[str, str] | None = None) -> list[Evidence]:
    titles, uris = document_titles or {}, source_uris or {}
    evidence: list[Evidence] = []
    seen: set[str] = set()
    for hit in hits:
        if hit.chunk.chunk_id in seen:
            continue
        seen.add(hit.chunk.chunk_id)
        evidence.append(Evidence(f"E{len(evidence)+1}", hit.chunk.document_id, hit.chunk.chunk_id, titles.get(hit.chunk.document_id, hit.chunk.document_id), hit.chunk.text, uris.get(hit.chunk.document_id, ""), hit.chunk.start_char, hit.chunk.end_char, hit.fused_score))
    return evidence

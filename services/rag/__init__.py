"""NEXUS RAG intelligence package."""

from .chunking import Chunk, chunk_text
from .embedding_cache import EmbeddingCache
from .embeddings import EmbeddingModel, EmbeddingProvider, EmbeddingVector, embed_batched
from .ranking import (
    RankedCandidate,
    compare_ranking_runs,
    diversify_by_group,
    filter_candidates,
    ranking_metrics,
    reciprocal_rank_fusion,
)
from .retrieval import Evidence, RetrievalHit, hybrid_retrieve
from .vector_store import InMemoryVectorStore, VectorMatch, VectorRecord, VectorStore

__all__ = [
    "Chunk",
    "EmbeddingCache",
    "EmbeddingModel",
    "EmbeddingProvider",
    "EmbeddingVector",
    "Evidence",
    "InMemoryVectorStore",
    "RankedCandidate",
    "RetrievalHit",
    "VectorMatch",
    "VectorRecord",
    "VectorStore",
    "chunk_text",
    "compare_ranking_runs",
    "diversify_by_group",
    "embed_batched",
    "filter_candidates",
    "hybrid_retrieve",
    "ranking_metrics",
    "reciprocal_rank_fusion",
]

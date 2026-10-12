"""NEXUS RAG intelligence package."""

from .chunking import Chunk, chunk_text
from .embedding_cache import EmbeddingCache
from .embeddings import EmbeddingModel, EmbeddingProvider, EmbeddingVector, embed_batched
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
    "RetrievalHit",
    "VectorMatch",
    "VectorRecord",
    "VectorStore",
    "chunk_text",
    "embed_batched",
    "hybrid_retrieve",
]

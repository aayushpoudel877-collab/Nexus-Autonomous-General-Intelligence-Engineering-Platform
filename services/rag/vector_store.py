"""Tenant-scoped vector-store contracts and a deterministic reference backend.

The in-memory implementation is intended for local development and tests only.
Production deployments should implement VectorStore using a durable backend with
tenant filtering enforced by the storage query, not by application-side filtering.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

from .embeddings import EmbeddingModel, EmbeddingVector


@dataclass(frozen=True, slots=True)
class VectorRecord:
    tenant_id: str
    document_id: str
    chunk_id: str
    text: str
    embedding: EmbeddingVector
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.tenant_id.strip() or not self.document_id.strip() or not self.chunk_id.strip():
            raise ValueError("tenant_id, document_id, and chunk_id are required")
        if not self.text.strip():
            raise ValueError("record text must be non-empty")


@dataclass(frozen=True, slots=True)
class VectorMatch:
    record: VectorRecord
    score: float


class VectorStore(Protocol):
    """Durable vector index contract; implementations must enforce tenant scope."""

    async def upsert(self, records: Sequence[VectorRecord]) -> None:
        """Insert or replace records by tenant and chunk identity."""

    async def search(
        self, *, tenant_id: str, query: EmbeddingVector, top_k: int = 5
    ) -> list[VectorMatch]:
        """Return nearest records for one tenant only."""

    async def delete_document(self, *, tenant_id: str, document_id: str) -> int:
        """Delete all indexed chunks for a document within the given tenant."""


class InMemoryVectorStore:
    """Small deterministic cosine-similarity backend for tests and local demos."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], VectorRecord] = {}

    async def upsert(self, records: Sequence[VectorRecord]) -> None:
        for record in records:
            self._check_model(record.embedding.model)
            key = (record.tenant_id, record.chunk_id)
            self._records[key] = record

    async def search(
        self, *, tenant_id: str, query: EmbeddingVector, top_k: int = 5
    ) -> list[VectorMatch]:
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not 1 <= top_k <= 100:
            raise ValueError("top_k must be between 1 and 100")
        matches = []
        for record in self._records.values():
            if record.tenant_id != tenant_id:
                continue
            self._check_model(record.embedding.model)
            if record.embedding.model != query.model:
                raise ValueError("cannot compare embeddings from different model versions")
            score = self._cosine(query.values, record.embedding.values)
            matches.append(VectorMatch(record=record, score=score))
        matches.sort(key=lambda match: (-match.score, match.record.document_id, match.record.chunk_id))
        return matches[:top_k]

    async def delete_document(self, *, tenant_id: str, document_id: str) -> int:
        if not tenant_id.strip() or not document_id.strip():
            raise ValueError("tenant_id and document_id are required")
        keys = [
            key for key, record in self._records.items()
            if record.tenant_id == tenant_id and record.document_id == document_id
        ]
        for key in keys:
            del self._records[key]
        return len(keys)

    def __len__(self) -> int:
        return len(self._records)

    def _check_model(self, model: EmbeddingModel) -> None:
        if any(
            record.embedding.model != model
            for record in self._records.values()
            if record.embedding.model.dimensions != model.dimensions
        ):
            raise ValueError("vector dimension mismatch")

    @staticmethod
    def _cosine(left: Iterable[float], right: Iterable[float]) -> float:
        left_values, right_values = tuple(left), tuple(right)
        if len(left_values) != len(right_values):
            raise ValueError("vector dimensions do not match")
        dot = sum(a * b for a, b in zip(left_values, right_values))
        left_norm = math.sqrt(sum(value * value for value in left_values))
        right_norm = math.sqrt(sum(value * value for value in right_values))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

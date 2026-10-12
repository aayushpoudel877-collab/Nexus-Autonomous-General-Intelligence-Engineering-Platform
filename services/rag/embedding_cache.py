"""Bounded tenant-scoped cache for validated embedding vectors."""
from __future__ import annotations

from collections import OrderedDict
from hashlib import sha256

from .embeddings import EmbeddingModel, EmbeddingVector


class EmbeddingCache:
    """Small in-process LRU cache keyed by tenant, model identity and content hash.

    The cache stores vectors rather than raw text. Tenant identity is part of the key
    so identical text from separate organizations is not implicitly shared. This is
    process-local only; distributed invalidation and persistence are out of scope.
    """

    def __init__(self, *, max_entries: int = 10_000) -> None:
        if not 1 <= max_entries <= 1_000_000:
            raise ValueError("max_entries must be between 1 and 1000000")
        self.max_entries = max_entries
        self._entries: OrderedDict[
            tuple[str, EmbeddingModel, str], EmbeddingVector
        ] = OrderedDict()

    def get(self, *, tenant_id: str, model: EmbeddingModel, text: str) -> EmbeddingVector | None:
        key = self._key(tenant_id=tenant_id, model=model, text=text)
        vector = self._entries.get(key)
        if vector is not None:
            self._entries.move_to_end(key)
        return vector

    def put(
        self, *, tenant_id: str, model: EmbeddingModel, text: str, vector: EmbeddingVector
    ) -> None:
        key = self._key(tenant_id=tenant_id, model=model, text=text)
        if vector.model != model:
            raise ValueError("vector model does not match cache key model")
        self._entries[key] = vector
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)

    def clear_tenant(self, *, tenant_id: str) -> int:
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        keys = [key for key in self._entries if key[0] == tenant_id]
        for key in keys:
            del self._entries[key]
        return len(keys)

    def __len__(self) -> int:
        return len(self._entries)

    @staticmethod
    def _key(*, tenant_id: str, model: EmbeddingModel, text: str) -> tuple[str, EmbeddingModel, str]:
        if not tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not text.strip():
            raise ValueError("text is required")
        digest = sha256(text.encode("utf-8")).hexdigest()
        return tenant_id, model, digest

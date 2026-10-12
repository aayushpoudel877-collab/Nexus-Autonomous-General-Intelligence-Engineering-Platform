"""Provider-neutral embedding contracts and bounded batch orchestration.

This module deliberately does not import a hosted model SDK. Provider integrations
implement EmbeddingProvider and are responsible for credentials, transport retries,
and provider-specific rate-limit headers. The orchestration layer validates results
before they can enter a vector index.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class EmbeddingModel:
    """Stable identity for an embedding model and its output space."""

    provider: str
    model: str
    version: str
    dimensions: int

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.model.strip() or not self.version.strip():
            raise ValueError("provider, model, and version must be non-empty")
        if self.dimensions < 1:
            raise ValueError("dimensions must be positive")


@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    """A validated vector tied to the exact model that produced it."""

    model: EmbeddingModel
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.values) != self.model.dimensions:
            raise ValueError("embedding dimensions do not match model metadata")
        if any(not math.isfinite(value) for value in self.values):
            raise ValueError("embedding values must be finite")


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Interface implemented by local or remote embedding providers."""

    @property
    def model(self) -> EmbeddingModel:
        """Return immutable provider/model/version/dimension metadata."""

    async def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        """Embed a non-empty batch and preserve input order."""


async def embed_batched(
    provider: EmbeddingProvider,
    texts: Sequence[str],
    *,
    batch_size: int = 32,
    max_text_chars: int = 20_000,
) -> list[EmbeddingVector]:
    """Embed texts in bounded batches while preserving exact input ordering.

    Empty input returns an empty list without calling the provider. Invalid input,
    malformed provider responses, non-finite values, and dimension mismatches fail
    closed. This function does not retry provider calls because safe retry semantics
    and rate limits vary by provider and must be supplied by a concrete adapter.
    """
    if not 1 <= batch_size <= 256:
        raise ValueError("batch_size must be between 1 and 256")
    if max_text_chars < 1:
        raise ValueError("max_text_chars must be positive")
    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("every text must be a non-empty string")
    if any(len(text) > max_text_chars for text in texts):
        raise ValueError("text exceeds max_text_chars")

    results: list[EmbeddingVector] = []
    model = provider.model
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        raw_vectors = await provider.embed(batch)
        if len(raw_vectors) != len(batch):
            raise ValueError("provider returned a different number of vectors than inputs")
        results.extend(
            EmbeddingVector(model=model, values=tuple(float(value) for value in vector))
            for vector in raw_vectors
        )
    return results

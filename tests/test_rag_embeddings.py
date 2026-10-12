from __future__ import annotations

import pytest

from services.rag.embeddings import (
    EmbeddingModel,
    EmbeddingVector,
    embed_batched,
)
from services.rag.vector_store import InMemoryVectorStore, VectorRecord


MODEL = EmbeddingModel(provider="test", model="tiny", version="v1", dimensions=2)


class FakeProvider:
    model = MODEL

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts):
        self.calls.append(list(texts))
        return [[float(len(text)), 1.0] for text in texts]


class WrongCountProvider(FakeProvider):
    async def embed(self, texts):
        return []


@pytest.mark.asyncio
async def test_embedding_batches_preserve_input_order():
    provider = FakeProvider()
    result = await embed_batched(provider, ["a", "bb", "ccc"], batch_size=2)

    assert [vector.values for vector in result] == [(1.0, 1.0), (2.0, 1.0), (3.0, 1.0)]
    assert provider.calls == [["a", "bb"], ["ccc"]]


@pytest.mark.asyncio
async def test_empty_embedding_input_does_not_call_provider():
    provider = FakeProvider()

    assert await embed_batched(provider, []) == []
    assert provider.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("batch_size", [0, -1, 257])
async def test_embedding_batch_size_is_bounded(batch_size):
    with pytest.raises(ValueError):
        await embed_batched(FakeProvider(), ["text"], batch_size=batch_size)


@pytest.mark.asyncio
async def test_embedding_rejects_empty_and_oversized_text():
    with pytest.raises(ValueError):
        await embed_batched(FakeProvider(), ["  "])
    with pytest.raises(ValueError):
        await embed_batched(FakeProvider(), ["too long"], max_text_chars=3)


@pytest.mark.asyncio
async def test_embedding_rejects_malformed_provider_response():
    with pytest.raises(ValueError, match="different number"):
        await embed_batched(WrongCountProvider(), ["text"])


def test_embedding_model_requires_identity_and_positive_dimensions():
    with pytest.raises(ValueError):
        EmbeddingModel(provider="", model="tiny", version="v1", dimensions=2)
    with pytest.raises(ValueError):
        EmbeddingModel(provider="test", model="tiny", version="v1", dimensions=0)


def test_embedding_vector_rejects_wrong_dimension_and_non_finite_values():
    with pytest.raises(ValueError):
        EmbeddingVector(MODEL, (1.0,))
    with pytest.raises(ValueError):
        EmbeddingVector(MODEL, (float("nan"), 0.0))


@pytest.mark.asyncio
async def test_vector_store_returns_nearest_match_within_tenant():
    store = InMemoryVectorStore()
    await store.upsert([
        VectorRecord("org-a", "doc-a", "chunk-a", "same direction", EmbeddingVector(MODEL, (1.0, 0.0))),
        VectorRecord("org-a", "doc-b", "chunk-b", "orthogonal", EmbeddingVector(MODEL, (0.0, 1.0))),
        VectorRecord("org-b", "doc-c", "chunk-c", "other tenant", EmbeddingVector(MODEL, (1.0, 0.0))),
    ])

    matches = await store.search(
        tenant_id="org-a", query=EmbeddingVector(MODEL, (1.0, 0.0)), top_k=5
    )

    assert [match.record.chunk_id for match in matches] == ["chunk-a", "chunk-b"]
    assert matches[0].score == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_vector_store_upsert_is_idempotent_for_tenant_chunk_key():
    store = InMemoryVectorStore()
    first = VectorRecord("org-a", "doc-a", "chunk-a", "old", EmbeddingVector(MODEL, (1.0, 0.0)))
    second = VectorRecord("org-a", "doc-a", "chunk-a", "new", EmbeddingVector(MODEL, (0.0, 1.0)))
    await store.upsert([first])
    await store.upsert([second])

    matches = await store.search(
        tenant_id="org-a", query=EmbeddingVector(MODEL, (0.0, 1.0))
    )
    assert len(store) == 1
    assert matches[0].record.text == "new"


@pytest.mark.asyncio
async def test_vector_store_rejects_mixed_model_versions():
    store = InMemoryVectorStore()
    different_model = EmbeddingModel(
        provider="test", model="tiny", version="v2", dimensions=2
    )
    records = [
        VectorRecord("org-a", "doc-a", "chunk-a", "a", EmbeddingVector(MODEL, (1.0, 0.0))),
        VectorRecord(
            "org-a", "doc-b", "chunk-b", "b",
            EmbeddingVector(different_model, (1.0, 0.0)),
        ),
    ]

    with pytest.raises(ValueError, match="model versions"):
        await store.upsert(records)
    assert len(store) == 0


@pytest.mark.asyncio
async def test_vector_store_delete_is_tenant_scoped():
    store = InMemoryVectorStore()
    await store.upsert([
        VectorRecord("org-a", "doc-a", "chunk-a", "a", EmbeddingVector(MODEL, (1.0, 0.0))),
        VectorRecord("org-b", "doc-a", "chunk-b", "b", EmbeddingVector(MODEL, (1.0, 0.0))),
    ])

    assert await store.delete_document(tenant_id="org-a", document_id="doc-a") == 1
    assert len(store) == 1
    assert (await store.search(
        tenant_id="org-b", query=EmbeddingVector(MODEL, (1.0, 0.0))
    ))[0].record.chunk_id == "chunk-b"


@pytest.mark.asyncio
async def test_vector_store_validates_query_and_record_inputs():
    store = InMemoryVectorStore()
    with pytest.raises(ValueError):
        await store.search(tenant_id="", query=EmbeddingVector(MODEL, (1.0, 0.0)))
    with pytest.raises(ValueError):
        await store.search(tenant_id="org-a", query=EmbeddingVector(MODEL, (1.0, 0.0)), top_k=0)
    with pytest.raises(ValueError):
        VectorRecord("", "doc", "chunk", "text", EmbeddingVector(MODEL, (1.0, 0.0)))

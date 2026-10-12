import pytest

from services.rag.embedding_cache import EmbeddingCache
from services.rag.embeddings import EmbeddingModel, EmbeddingVector


MODEL = EmbeddingModel(provider="test", model="tiny", version="v1", dimensions=2)


def test_cache_is_tenant_scoped_and_does_not_store_raw_text():
    cache = EmbeddingCache(max_entries=3)
    vector = EmbeddingVector(MODEL, (0.2, 0.8))
    cache.put(tenant_id="org-a", model=MODEL, text="private notes", vector=vector)

    assert cache.get(tenant_id="org-a", model=MODEL, text="private notes") == vector
    assert cache.get(tenant_id="org-b", model=MODEL, text="private notes") is None
    assert "private notes" not in repr(cache._entries)


def test_cache_key_tracks_model_version():
    cache = EmbeddingCache()
    vector = EmbeddingVector(MODEL, (0.2, 0.8))
    cache.put(tenant_id="org-a", model=MODEL, text="notes", vector=vector)
    next_model = EmbeddingModel(provider="test", model="tiny", version="v2", dimensions=2)

    assert cache.get(tenant_id="org-a", model=next_model, text="notes") is None


def test_cache_evicts_least_recently_used_entry():
    cache = EmbeddingCache(max_entries=2)
    first = EmbeddingVector(MODEL, (1.0, 0.0))
    second = EmbeddingVector(MODEL, (0.0, 1.0))
    cache.put(tenant_id="org", model=MODEL, text="first", vector=first)
    cache.put(tenant_id="org", model=MODEL, text="second", vector=second)
    assert cache.get(tenant_id="org", model=MODEL, text="first") == first
    cache.put(tenant_id="org", model=MODEL, text="third", vector=first)

    assert cache.get(tenant_id="org", model=MODEL, text="first") == first
    assert cache.get(tenant_id="org", model=MODEL, text="second") is None
    assert len(cache) == 2


def test_cache_rejects_model_mismatch_and_clears_only_one_tenant():
    cache = EmbeddingCache()
    vector = EmbeddingVector(MODEL, (1.0, 0.0))
    cache.put(tenant_id="org-a", model=MODEL, text="same", vector=vector)
    cache.put(tenant_id="org-b", model=MODEL, text="same", vector=vector)
    next_model = EmbeddingModel(provider="test", model="tiny", version="v2", dimensions=2)

    with pytest.raises(ValueError, match="does not match"):
        cache.put(tenant_id="org-a", model=next_model, text="wrong model", vector=vector)
    assert cache.clear_tenant(tenant_id="org-a") == 1
    assert cache.get(tenant_id="org-b", model=MODEL, text="same") == vector


def test_cache_requires_valid_capacity_and_keys():
    with pytest.raises(ValueError):
        EmbeddingCache(max_entries=0)
    cache = EmbeddingCache()
    vector = EmbeddingVector(MODEL, (1.0, 0.0))
    with pytest.raises(ValueError):
        cache.put(tenant_id="", model=MODEL, text="text", vector=vector)
    with pytest.raises(ValueError):
        cache.get(tenant_id="org", model=MODEL, text=" ")

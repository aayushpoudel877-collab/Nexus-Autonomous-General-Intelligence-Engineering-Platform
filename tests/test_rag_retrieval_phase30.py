import pytest

from services.rag.chunking import Chunk
from services.rag.retrieval import hybrid_retrieve, pack_evidence


def make_chunk(chunk_id, document_id, tenant_id, text, ordinal=0):
    return Chunk(
        chunk_id=chunk_id,
        document_id=document_id,
        tenant_id=tenant_id,
        text=text,
        start_char=0,
        end_char=len(text),
        ordinal=ordinal,
    )


@pytest.fixture
def corpus():
    return [
        make_chunk("a1", "doc-a", "org-a", "neural networks classify images", 0),
        make_chunk("a2", "doc-a", "org-a", "neural networks classify documents", 1),
        make_chunk("b1", "doc-b", "org-a", "neural network optimization", 0),
        make_chunk("c1", "doc-c", "org-b", "neural networks classify images", 0),
        make_chunk("d1", "doc-d", "org-a", "gardening and soil", 0),
    ]


def test_retrieval_filters_to_tenant_and_allowed_documents(corpus):
    hits = hybrid_retrieve(
        "neural networks",
        corpus,
        tenant_id="org-a",
        allowed_document_ids={"doc-b", "doc-d"},
    )
    assert hits
    assert {hit.chunk.document_id for hit in hits} == {"doc-b"}


def test_retrieval_excludes_documents_before_ranking(corpus):
    hits = hybrid_retrieve(
        "neural networks",
        corpus,
        tenant_id="org-a",
        excluded_document_ids={"doc-a"},
    )
    assert all(hit.chunk.document_id != "doc-a" for hit in hits)
    assert all(hit.chunk.tenant_id == "org-a" for hit in hits)


def test_retrieval_diversifies_per_document(corpus):
    hits = hybrid_retrieve(
        "neural networks classify",
        corpus,
        tenant_id="org-a",
        top_k=3,
        per_document_limit=1,
    )
    ids = [hit.chunk.document_id for hit in hits]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"bm25_k1": 0},
        {"bm25_b": 1.5},
        {"per_document_limit": 0},
        {"lexical_weight": float("nan")},
    ],
)
def test_retrieval_rejects_invalid_ranking_configuration(corpus, kwargs):
    with pytest.raises(ValueError):
        hybrid_retrieve("neural networks", corpus, tenant_id="org-a", **kwargs)


def test_retrieval_rejects_non_finite_dense_scores(corpus):
    with pytest.raises(ValueError):
        hybrid_retrieve(
            "neural networks",
            corpus,
            tenant_id="org-a",
            dense_scores={"a1": float("nan")},
        )


def test_retrieval_supports_tunable_bm25(corpus):
    default = hybrid_retrieve("neural networks", corpus, tenant_id="org-a")
    tuned = hybrid_retrieve(
        "neural networks", corpus, tenant_id="org-a", bm25_k1=1.8, bm25_b=0.2
    )
    assert default
    assert tuned
    assert {hit.chunk.chunk_id for hit in default} == {hit.chunk.chunk_id for hit in tuned}


def test_evidence_packing_keeps_unique_source_references(corpus):
    hits = hybrid_retrieve("neural networks", corpus, tenant_id="org-a")
    evidence = pack_evidence(
        hits,
        document_titles={"doc-a": "Neural Systems"},
        source_uris={"doc-a": "https://example.invalid/source"},
    )
    assert len({item.chunk_id for item in evidence}) == len(evidence)
    if evidence:
        first = evidence[0]
        assert first.evidence_id == "E1"

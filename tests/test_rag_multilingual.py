import pytest

from services.rag.chunking import chunk_text
from services.rag.retrieval import hybrid_retrieve, tokenize


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hello, WORLD! 123", ["hello", "world", "123"]),
        ("नेपालको राजधानी काठमाडौं हो", ["नेपालको", "राजधानी", "काठमाडौं", "हो"]),
        ("नमस्ते दुनिया", ["नमस्ते", "दुनिया"]),
        ("مرحبا بالعالم", ["مرحبا", "بالعالم"]),
        ("Привет, мир!", ["привет", "мир"]),
        ("こんにちは 世界", ["こんにちは", "世界"]),
        ("café cafe\u0301", ["café", "café"]),
        ("foo_bar baz", ["foo_bar", "baz"]),
    ],
)
def test_unicode_tokenizer_preserves_multilingual_words(text, expected):
    assert tokenize(text) == expected


def test_unicode_tokenizer_handles_empty_and_punctuation_only_text():
    assert tokenize("") == []
    assert tokenize("— … !") == []


def test_unicode_tokenizer_requires_string_input():
    with pytest.raises(TypeError, match="text must be a string"):
        tokenize(None)


def test_bm25_retrieves_devanagari_chunks_without_changing_tenant_scope():
    nepali = chunk_text("नेपालको राजधानी काठमाडौं हो", "doc-ne", "org-a")
    english = chunk_text("The capital of France is Paris", "doc-en", "org-a")
    other_tenant = chunk_text("नेपालको राजधानी काठमाडौं हो", "doc-other", "org-b")

    hits = hybrid_retrieve(
        "काठमाडौं राजधानी",
        [*english, *nepali, *other_tenant],
        tenant_id="org-a",
        top_k=5,
    )

    assert hits
    assert hits[0].chunk.document_id == "doc-ne"
    assert all(hit.chunk.tenant_id == "org-a" for hit in hits)

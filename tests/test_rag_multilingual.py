import pytest

from services.rag.chunking import chunk_text
from services.rag.retrieval import (
    character_ngram_similarity,
    character_ngrams,
    hybrid_retrieve,
    tokenize,
)


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



def test_character_ngrams_support_scripts_without_whitespace_segmentation():
    assert character_ngram_similarity("東京", "東京大学の図書館") == 1.0
    assert character_ngram_similarity("काठमाडौं", "काठमाडौंमा पुस्तकालय") > 0.0
    assert character_ngram_similarity("東京", "大阪大学") == 0.0


def test_character_ngrams_validate_bounds_and_handle_short_queries():
    assert character_ngrams("中", min_n=2, max_n=4) == {"中"}
    assert character_ngrams("ＡＢＣ", min_n=2, max_n=2) == {"ab", "bc"}
    with pytest.raises(ValueError, match="n-gram bounds"):
        character_ngrams("text", min_n=0, max_n=2)
    with pytest.raises(ValueError, match="n-gram bounds"):
        character_ngrams("text", min_n=3, max_n=2)


def test_character_ngram_retrieval_is_opt_in_and_respects_tenant_scope():
    tokyo = chunk_text("東京大学の図書館", "doc-tokyo", "org-a")
    osaka = chunk_text("大阪大学の図書館", "doc-osaka", "org-a")
    other_tenant = chunk_text("東京大学の図書館", "doc-private", "org-b")

    default_hits = hybrid_retrieve(
        "東京", [*tokyo, *osaka, *other_tenant], tenant_id="org-a", top_k=5
    )
    assert default_hits == []

    hits = hybrid_retrieve(
        "東京",
        [*tokyo, *osaka, *other_tenant],
        tenant_id="org-a",
        top_k=5,
        character_ngram_weight=0.4,
    )
    assert hits
    assert hits[0].chunk.document_id == "doc-tokyo"
    assert hits[0].character_ngram_score == 1.0
    assert all(hit.chunk.tenant_id == "org-a" for hit in hits)


@pytest.mark.parametrize("weight", [-0.01, 1.01, float("nan"), float("inf")])
def test_character_ngram_weight_must_be_finite_and_bounded(weight):
    with pytest.raises(ValueError, match="character_ngram_weight"):
        hybrid_retrieve(
            "query", [], tenant_id="org-a", character_ngram_weight=weight
        )

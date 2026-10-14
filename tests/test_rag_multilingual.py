import pytest

from services.rag.retrieval import tokenize


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

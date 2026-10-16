import pytest

from services.rag.multimodal_index import (
    MAX_REPRESENTATION_CHARS,
    MultimodalRepresentation,
    index_representation,
)


def _representation(**overrides):
    values = {
        "representation_id": "caption-1",
        "tenant_id": "org-1",
        "asset_id": "asset-1",
        "modality": "image",
        "kind": "caption",
        "text": "A street scene with signs in Nepali.",
        "language": "ne",
    }
    values.update(overrides)
    return MultimodalRepresentation(**values)


def test_image_caption_becomes_tenant_scoped_retrieval_chunks():
    indexed = index_representation(_representation(), max_chars=12, overlap=2)
    assert len(indexed) > 1
    assert all(item.chunk.tenant_id == "org-1" for item in indexed)
    assert all(item.chunk.document_id == "asset-1" for item in indexed)
    assert all(item.modality == "image" and item.kind == "caption" for item in indexed)
    assert [item.chunk.ordinal for item in indexed] == list(range(len(indexed)))
    assert len({item.chunk.chunk_id for item in indexed}) == len(indexed)


def test_audio_transcript_preserves_time_provenance():
    item = _representation(
        modality="audio",
        kind="transcript",
        start_ms=1_200,
        end_ms=3_400,
        text="The speaker describes the first experiment.",
    )
    indexed = index_representation(item)
    assert indexed[0].start_ms == 1_200
    assert indexed[0].end_ms == 3_400
    assert indexed[0].chunk.start_char == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"modality": "image", "kind": "transcript"},
        {"modality": "audio", "kind": "ocr"},
        {"modality": "text", "kind": "caption"},
        {"modality": "audio", "start_ms": 50},
        {"modality": "video", "start_ms": 200, "end_ms": 100},
        {"modality": "image", "start_ms": 0, "end_ms": 10},
        {"page_number": 0},
        {"metadata": (("api_token", "sensitive"),)},
        {"metadata": (("language", "ne"), ("LANGUAGE", "en"))},
    ],
)
def test_invalid_representation_contracts_fail_closed(overrides):
    with pytest.raises(ValueError):
        _representation(**overrides)


def test_text_limit_is_enforced_before_chunking():
    with pytest.raises(ValueError, match="maximum character limit"):
        _representation(text="x" * (MAX_REPRESENTATION_CHARS + 1))


def test_metadata_bounds_are_enforced():
    with pytest.raises(ValueError, match="too many fields"):
        _representation(metadata=tuple((f"k{i}", "v") for i in range(33)))
    with pytest.raises(ValueError, match="maximum encoded size"):
        _representation(metadata=tuple((f"field_{index}", "x" * 1_000) for index in range(9)))


def test_chunk_bounds_are_validated():
    with pytest.raises(ValueError, match="max_chars"):
        index_representation(_representation(), max_chars=10, overlap=10)


def test_representation_ids_keep_distinct_sources_for_same_asset():
    first = index_representation(_representation(representation_id="caption"))
    second = index_representation(_representation(representation_id="ocr", kind="ocr"))
    assert first[0].chunk.chunk_id != second[0].chunk.chunk_id
    assert first[0].chunk.document_id == second[0].chunk.document_id

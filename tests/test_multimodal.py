import pytest
from pydantic import ValidationError

from services.api.app.schemas.multimodal import MultimodalAssetCreate


def test_text_asset_manifest_accepts_bounded_metadata():
    asset = MultimodalAssetCreate(
        name="Nepali sample",
        modality="text",
        source_reference="dataset://nepali/train/001",
        media_type="text/plain",
        sha256="a" * 64,
        byte_size=128,
        metadata={"language": "ne", "split": "train", "verified": True},
    )
    assert asset.modality == "text"
    assert asset.metadata["language"] == "ne"


def test_image_asset_requires_image_media_type():
    with pytest.raises(ValidationError, match="image/"):
        MultimodalAssetCreate(
            name="Sample image",
            modality="image",
            source_reference="asset://images/one",
            media_type="text/plain",
        )


def test_audio_and_video_metadata_are_modality_specific():
    audio = MultimodalAssetCreate(
        name="Audio clip",
        modality="audio",
        source_reference="asset://audio/one",
        media_type="audio/wav",
        duration_ms=1200,
    )
    assert audio.duration_ms == 1200

    with pytest.raises(ValidationError, match="only valid for audio or video"):
        MultimodalAssetCreate(
            name="Text with duration",
            modality="text",
            source_reference="asset://text/one",
            media_type="text/plain",
            duration_ms=100,
        )


def test_asset_hash_and_size_are_validated():
    with pytest.raises(ValidationError):
        MultimodalAssetCreate(
            name="Bad checksum",
            modality="text",
            source_reference="asset://text/one",
            media_type="text/plain",
            sha256="not-a-checksum",
        )
    with pytest.raises(ValidationError):
        MultimodalAssetCreate(
            name="Negative size",
            modality="text",
            source_reference="asset://text/one",
            media_type="text/plain",
            byte_size=-1,
        )


def test_asset_manifest_limits_metadata_fields():
    metadata = {f"field_{index}": index for index in range(51)}
    with pytest.raises(ValidationError):
        MultimodalAssetCreate(
            name="Too much metadata",
            modality="structured",
            source_reference="asset://records/one",
            media_type="application/json",
            metadata=metadata,
        )

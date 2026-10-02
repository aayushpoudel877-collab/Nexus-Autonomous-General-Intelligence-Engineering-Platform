import pytest
from types import SimpleNamespace

from pydantic import ValidationError

from services.api.app.schemas.multimodal import MultimodalAssetCreate, MultimodalAssetRead


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


def test_asset_metadata_values_are_bounded():
    with pytest.raises(ValidationError, match="16 KiB"):
        MultimodalAssetCreate(
            name="Large metadata",
            modality="text",
            source_reference="asset://text/one",
            media_type="text/plain",
            metadata={"description": "x" * 17000},
        )
    with pytest.raises(ValidationError, match="keys must be"):
        MultimodalAssetCreate(
            name="Bad metadata key",
            modality="text",
            source_reference="asset://text/one",
            media_type="text/plain",
            metadata={"": "value"},
        )


def test_asset_read_schema_serializes_metadata_json_attribute():
    from datetime import datetime, timezone
    from uuid import uuid4

    record = SimpleNamespace(
        id=uuid4(), project_id=uuid4(), owner_id=uuid4(), name="Sample", modality="text",
        source_reference="asset://text/one", media_type="text/plain", sha256=None,
        byte_size=None, duration_ms=None, width=None, height=None,
        metadata_json={"language": "ne"}, created_at=datetime.now(timezone.utc),
    )
    assert MultimodalAssetRead.model_validate(record).metadata == {"language": "ne"}


def test_source_reference_rejects_network_and_local_file_urls():
    for reference in ("https://example.com/asset", "http://127.0.0.1/admin", "file:///etc/passwd"):
        with pytest.raises(ValidationError, match="approved"):
            MultimodalAssetCreate(
                name="Unsafe reference", modality="text", source_reference=reference,
                media_type="text/plain",
            )


def test_source_reference_rejects_credentials_and_query_strings():
    for reference in ("s3://user:secret@bucket/object", "asset://catalog/item?token=secret"):
        with pytest.raises(ValidationError, match="credentials"):
            MultimodalAssetCreate(
                name="Unsafe reference", modality="text", source_reference=reference,
                media_type="text/plain",
            )


def test_source_reference_accepts_logical_asset_and_dataset_uris():
    for reference in ("asset://images/sample", "dataset://nepali/train/001", "s3://bucket/data/item"):
        asset = MultimodalAssetCreate(
            name="Safe reference", modality="text", source_reference=reference,
            media_type="text/plain",
        )
        assert asset.source_reference == reference

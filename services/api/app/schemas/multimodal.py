from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Modality = Literal["text", "image", "audio", "video", "structured"]


class MultimodalAssetCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    modality: Modality
    source_reference: str = Field(min_length=1, max_length=2048)
    media_type: str = Field(
        min_length=3, max_length=120, pattern=r"^[A-Za-z0-9.+-]+/[A-Za-z0-9.+-]+$"
    )
    sha256: str | None = Field(default=None, pattern=r"^[A-Fa-f0-9]{64}$")
    byte_size: int | None = Field(default=None, ge=0, le=10**15)
    duration_ms: int | None = Field(default=None, ge=0, le=10**12)
    width: int | None = Field(default=None, gt=0, le=1_000_000)
    height: int | None = Field(default=None, gt=0, le=1_000_000)
    metadata: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict, max_length=50
    )

    @field_validator("name", "source_reference", "media_type")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_modality_metadata(self) -> "MultimodalAssetCreate":
        if self.modality not in {"audio", "video"} and self.duration_ms is not None:
            raise ValueError("duration_ms is only valid for audio or video assets")
        if self.modality not in {"image", "video"} and (
            self.width is not None or self.height is not None
        ):
            raise ValueError("width and height are only valid for image or video assets")
        if self.modality == "image" and not self.media_type.lower().startswith("image/"):
            raise ValueError("Image assets must use an image/* media type")
        if self.modality == "audio" and not self.media_type.lower().startswith("audio/"):
            raise ValueError("Audio assets must use an audio/* media type")
        if self.modality == "video" and not self.media_type.lower().startswith("video/"):
            raise ValueError("Video assets must use a video/* media type")
        if self.modality == "text" and not (
            self.media_type.lower().startswith("text/")
            or self.media_type.lower() in {"application/json", "application/pdf"}
        ):
            raise ValueError("Text assets must use a text/*, application/json, or application/pdf media type")
        return self


class MultimodalAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    owner_id: UUID
    name: str
    modality: Modality
    source_reference: str
    media_type: str
    sha256: str | None
    byte_size: int | None
    duration_ms: int | None
    width: int | None
    height: int | None
    metadata: dict = Field(validation_alias="metadata_json")
    created_at: datetime

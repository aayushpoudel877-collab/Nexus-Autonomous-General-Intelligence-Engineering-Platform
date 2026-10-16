"""Validated text representations for tenant-scoped multimodal retrieval.

This layer indexes extracted text (captions, transcripts, OCR, and document text),
not raw binary media. Provider-backed transcription/OCR and durable vector indexing
remain separate integrations.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Literal
from urllib.parse import quote

from .chunking import Chunk, chunk_text

Modality = Literal["text", "image", "audio", "video", "structured"]
RepresentationKind = Literal["extracted_text", "caption", "transcript", "ocr", "metadata"]

MAX_REPRESENTATION_CHARS = 200_000
MAX_METADATA_BYTES = 8_192
MAX_METADATA_FIELDS = 32
_ALLOWED_KINDS: dict[str, set[str]] = {
    "text": {"extracted_text", "metadata"},
    "image": {"caption", "ocr", "metadata"},
    "audio": {"transcript", "caption", "metadata"},
    "video": {"transcript", "caption", "ocr", "metadata"},
    "structured": {"extracted_text", "metadata"},
}
_SECRET_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "credential",
    "authorization",
    "apikey",
    "privatekey",
    "accesskey",
    "bearer",
    "cookie",
    "session",
)


def _sensitive_metadata_key(key: str) -> bool:
    compact = "".join(character for character in key.casefold() if character.isalnum())
    tokens = set(compact.split())
    return any(part in compact for part in _SECRET_KEY_PARTS) or compact == "auth" or (
        "api" in tokens and "key" in tokens
    )


def _representation_prefix(asset_id: str, representation_id: str) -> str:
    """Encode delimiters so distinct asset/representation pairs cannot collide."""
    return f"{quote(asset_id, safe='')}:{quote(representation_id, safe='')}"


@dataclass(frozen=True, slots=True)
class MultimodalRepresentation:
    """A bounded text view of a media asset with explicit provenance."""

    representation_id: str
    tenant_id: str
    asset_id: str
    modality: Modality
    kind: RepresentationKind
    text: str
    language: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    page_number: int | None = None
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        for name in ("representation_id", "tenant_id", "asset_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 200:
                raise ValueError(f"{name} must be a non-empty string of at most 200 characters")
        if self.modality not in _ALLOWED_KINDS:
            raise ValueError("unsupported modality")
        if self.kind not in _ALLOWED_KINDS[self.modality]:
            raise ValueError("representation kind is not valid for this modality")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("representation text must not be blank")
        if len(self.text) > MAX_REPRESENTATION_CHARS:
            raise ValueError("representation text exceeds the maximum character limit")
        if self.language is not None and (
            not self.language.strip() or len(self.language) > 35
        ):
            raise ValueError("language must be non-empty and at most 35 characters")
        if self.modality not in {"audio", "video"} and (
            self.start_ms is not None or self.end_ms is not None
        ):
            raise ValueError("timestamps are only valid for audio or video representations")
        if (self.start_ms is None) != (self.end_ms is None):
            raise ValueError("start_ms and end_ms must be provided together")
        if self.start_ms is not None and (
            isinstance(self.start_ms, bool)
            or isinstance(self.end_ms, bool)
            or not isinstance(self.start_ms, int)
            or not isinstance(self.end_ms, int)
            or self.start_ms < 0
            or self.end_ms <= self.start_ms
        ):
            raise ValueError("timestamps must be integers satisfying 0 <= start_ms < end_ms")
        if self.page_number is not None and (
            isinstance(self.page_number, bool)
            or not isinstance(self.page_number, int)
            or self.page_number < 1
            or self.modality not in {"text", "image", "video", "structured"}
        ):
            raise ValueError("page_number must be a positive integer for page-based modalities")
        if len(self.metadata) > MAX_METADATA_FIELDS:
            raise ValueError("metadata has too many fields")
        seen: set[str] = set()
        for entry in self.metadata:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise ValueError("metadata entries must be key/value pairs")
            key, value = entry
            if not isinstance(key, str) or not isinstance(value, str):
                raise TypeError("metadata keys and values must be strings")
            normalized_key = key.strip().casefold()
            if not normalized_key or len(key) > 80 or len(value) > 1024:
                raise ValueError("metadata keys and values exceed allowed bounds")
            if _sensitive_metadata_key(normalized_key):
                raise ValueError("credential-like metadata keys are not allowed")
            if normalized_key in seen:
                raise ValueError("metadata keys must be unique")
            seen.add(normalized_key)
        try:
            metadata_size = len(json.dumps(self.metadata, ensure_ascii=False).encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must be serializable") from exc
        if metadata_size > MAX_METADATA_BYTES:
            raise ValueError("metadata exceeds the maximum encoded size")


@dataclass(frozen=True, slots=True)
class IndexedMultimodalChunk:
    """A normal retrieval chunk plus its source representation provenance."""

    chunk: Chunk
    representation_id: str
    modality: Modality
    kind: RepresentationKind
    language: str | None
    start_ms: int | None
    end_ms: int | None
    page_number: int | None


def index_representation(
    representation: MultimodalRepresentation,
    *,
    max_chars: int = 1_200,
    overlap: int = 160,
) -> list[IndexedMultimodalChunk]:
    """Convert one representation into stable, bounded retrieval chunks."""
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 1:
        raise ValueError("max_chars must be a positive integer")
    if isinstance(overlap, bool) or not isinstance(overlap, int) or overlap < 0 or overlap >= max_chars:
        raise ValueError("overlap must be an integer smaller than max_chars and not negative")
    stable_prefix = _representation_prefix(
        representation.asset_id, representation.representation_id
    )
    internal_document_id = stable_prefix
    chunks = chunk_text(
        representation.text,
        document_id=internal_document_id,
        tenant_id=representation.tenant_id,
        max_chars=max_chars,
        overlap=overlap,
    )
    return [
        IndexedMultimodalChunk(
            chunk=Chunk(
                chunk_id=f"{stable_prefix}:{item.ordinal}",
                document_id=representation.asset_id,
                tenant_id=representation.tenant_id,
                text=item.text,
                start_char=item.start_char,
                end_char=item.end_char,
                ordinal=item.ordinal,
            ),
            representation_id=representation.representation_id,
            modality=representation.modality,
            kind=representation.kind,
            language=representation.language,
            start_ms=representation.start_ms,
            end_ms=representation.end_ms,
            page_number=representation.page_number,
        )
        for item in chunks
    ]

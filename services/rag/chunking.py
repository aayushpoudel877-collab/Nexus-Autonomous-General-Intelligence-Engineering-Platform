"""Deterministic text chunking that preserves original character offsets."""
from __future__ import annotations
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    tenant_id: str
    text: str
    start_char: int
    end_char: int
    ordinal: int

def normalize_text(text: str) -> str:
    """Normalize line endings and horizontal whitespace without deleting paragraphs."""
    text = text.replace("\\r\\n", "\\n").replace("\\r", "\\n")
    text = re.sub(r"[\\t\\f\\v ]+", " ", text)
    text = re.sub(r" *\\n *", "\\n", text)
    return text.strip()

def chunk_text(text: str, document_id: str, tenant_id: str, *, max_chars: int = 1200, overlap: int = 160) -> list[Chunk]:
    """Split normalized text into bounded chunks, preferring paragraph/sentence boundaries.

    Offsets refer to the normalized text returned by normalize_text, not the raw input.
    """
    if not document_id.strip() or not tenant_id.strip():
        raise ValueError("document_id and tenant_id are required")
    if max_chars < 1 or overlap < 0 or overlap >= max_chars:
        raise ValueError("require max_chars >= 1 and 0 <= overlap < max_chars")
    normalized = normalize_text(text)
    if not normalized:
        return []
    chunks: list[Chunk] = []
    start, ordinal = 0, 0
    while start < len(normalized):
        hard_end = min(start + max_chars, len(normalized))
        end = hard_end
        if hard_end < len(normalized):
            floor = start + max(1, max_chars // 2)
            candidates = [normalized.rfind("\\n\\n", floor, hard_end), normalized.rfind(". ", floor, hard_end), normalized.rfind(" ", floor, hard_end)]
            boundary = max(candidates)
            if boundary >= floor:
                end = boundary + (2 if normalized[boundary:boundary+2] == "\\n\\n" or normalized[boundary:boundary+2] == ". " else 1)
        body = normalized[start:end].strip()
        if body:
            left = start + len(normalized[start:end]) - len(normalized[start:end].lstrip())
            right = left + len(body)
            chunks.append(Chunk(f"{document_id}:{ordinal}", document_id, tenant_id, body, left, right, ordinal))
            ordinal += 1
        if end >= len(normalized):
            break
        start = max(start + 1, end - overlap)
    return chunks

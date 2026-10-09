"""Small, dependency-free contracts for tenant-scoped RAG records."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class Document:
    document_id: str
    tenant_id: str
    title: str
    text: str
    source_uri: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("document_id", "tenant_id", "title"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")

@dataclass(frozen=True)
class QueryRequest:
    tenant_id: str
    query: str
    top_k: int = 5
    dense_scores: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("tenant_id must not be empty")
        if not self.query.strip():
            raise ValueError("query must not be empty")
        if not 1 <= self.top_k <= 100:
            raise ValueError("top_k must be between 1 and 100")
        if any(not (-1.0 <= score <= 1.0) for score in self.dense_scores.values()):
            raise ValueError("dense scores must be between -1 and 1")

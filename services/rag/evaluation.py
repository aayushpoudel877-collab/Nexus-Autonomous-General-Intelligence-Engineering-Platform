"""Small, deterministic retrieval/grounding evaluation metrics."""
from __future__ import annotations
from dataclasses import dataclass
from .retrieval import RetrievalHit, Evidence
from .grounding import validate_citations

@dataclass(frozen=True)
class RetrievalMetrics:
    recall_at_k: float
    reciprocal_rank: float
    retrieved: int
    relevant_found: int

def evaluate_retrieval(hits: list[RetrievalHit], relevant_chunk_ids: set[str], *, k: int | None = None) -> RetrievalMetrics:
    considered = hits[:k] if k is not None else hits
    found = {hit.chunk.chunk_id for hit in considered} & relevant_chunk_ids
    rank = next((i for i, hit in enumerate(considered, 1) if hit.chunk.chunk_id in relevant_chunk_ids), None)
    recall = len(found) / len(relevant_chunk_ids) if relevant_chunk_ids else 1.0
    return RetrievalMetrics(recall, 1 / rank if rank else 0.0, len(considered), len(found))

def evaluate_grounding(answer: str, evidence: list[Evidence]) -> dict[str, object]:
    report = validate_citations(answer, evidence)
    return {"valid_citation_structure": report.valid, "citation_coverage": 1.0 if report.has_citation else 0.0, "unknown_citations": list(report.unknown_citations), "note": report.reason}

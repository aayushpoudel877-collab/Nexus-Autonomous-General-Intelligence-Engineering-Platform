"""NEXUS RAG intelligence package."""

from .chunking import Chunk, chunk_text
from .embedding_cache import EmbeddingCache
from .embeddings import EmbeddingModel, EmbeddingProvider, EmbeddingVector, embed_batched
from .evaluation import (\n    EvaluationCase,\n    EvaluationPrediction,\n    EvaluationThresholds,\n    build_evaluation_report,\n    compare_runs,\n    evaluate_golden_runs,\n    load_golden_dataset,\n    load_predictions,\n    write_report,\n)\nfrom .generation import (
    GenerationAnswer,
    GenerationEvidence,
    GenerationProvider,
    GenerationRequest,
    ProviderGeneration,
    generate_grounded_answer,
)
from .grounding import (
    CitationValidationReport,
    ClaimEvidence,
    ClaimGroundingReport,
    ClaimGroundingVerifier,
    GroundingAssessment,
    GroundingClaim,
    GroundingReport,
    LexicalGroundingVerifier,
    evidence_prompt_block,
    validate_citations,
)
from .ranking import (
    RankedCandidate,
    compare_ranking_runs,
    diversify_by_group,
    filter_candidates,
    ranking_metrics,
    reciprocal_rank_fusion,
)
from .retrieval import Evidence, RetrievalHit, hybrid_retrieve
from .vector_store import InMemoryVectorStore, VectorMatch, VectorRecord, VectorStore

__all__ = [
    "Chunk",
    "CitationValidationReport",
    "ClaimEvidence",
    "ClaimGroundingReport",
    "ClaimGroundingVerifier",
    "EmbeddingCache",
    "EmbeddingModel",
    "EmbeddingProvider",
    "EmbeddingVector",
    "Evidence",
    "GenerationAnswer",
    "GenerationEvidence",
    "GenerationProvider",
    "GenerationRequest",
    "GroundingAssessment",
    "GroundingClaim",
    "GroundingReport",
    "InMemoryVectorStore",
    "LexicalGroundingVerifier",
    "ProviderGeneration",
    "RankedCandidate",
    "RetrievalHit",
    "VectorMatch",
    "VectorRecord",
    "VectorStore",
    "chunk_text",
    "compare_ranking_runs",
    "diversify_by_group",
    "embed_batched",
    "evidence_prompt_block",
    "filter_candidates",
    "generate_grounded_answer",
    "hybrid_retrieve",
    "ranking_metrics",
    "reciprocal_rank_fusion",
    "validate_citations",
]

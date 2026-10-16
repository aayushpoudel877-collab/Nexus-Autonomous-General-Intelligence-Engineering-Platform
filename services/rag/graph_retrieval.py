"""Bounded graph-assisted candidate expansion for tenant-scoped RAG.

Consumes explicitly supplied entity/chunk associations. It does not extract entities
with a model, execute arbitrary graph queries, or replace lexical retrieval.
"""
from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
import math
from dataclasses import dataclass

from .ranking import RankedCandidate

MAX_GRAPH_EDGES = 20_000
MAX_GRAPH_ENTITIES = 20_000
MAX_GRAPH_SEEDS = 200
MAX_ENTITY_CHUNK_ASSOCIATIONS = 100_000
MAX_ENTITIES_PER_CHUNK = 32
MAX_CHUNKS_PER_ENTITY = 500
MAX_GRAPH_HOPS = 2


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """A reviewed relationship between two entity IDs within one tenant."""

    tenant_id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str

    def __post_init__(self) -> None:
        for name in ("tenant_id", "source_entity_id", "target_entity_id", "relation_type"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 200:
                raise ValueError(f"{name} must be a non-empty string of at most 200 characters")
        if self.source_entity_id == self.target_entity_id:
            raise ValueError("self-referential graph edges are not supported")


@dataclass(frozen=True, slots=True)
class GraphCandidate:
    """Candidate ranking plus a bounded explanation of its graph path."""

    candidate_id: str
    score: float
    seed_candidate_id: str
    entity_path: tuple[str, ...]
    relation_path: tuple[str, ...]
    hop_count: int


def graph_assisted_retrieve(
    seed_candidates: Sequence[RankedCandidate],
    edges: Sequence[GraphEdge],
    entity_chunk_ids: Mapping[str, Sequence[str]],
    *,
    tenant_id: str,
    chunk_tenants: Mapping[str, str],
    entity_tenants: Mapping[str, str],
    top_k: int = 10,
    max_hops: int = 1,
    decay: float = 0.65,
) -> list[GraphCandidate]:
    """Expand ranked seed chunks over an explicit, tenant-scoped entity graph.

    A seed chunk is connected to every entity whose entity_chunk_ids includes that
    chunk. Traversal follows graph edges in either direction. Newly discovered chunks
    receive seed_score * decay**hops; the strongest path wins. Results are ordered by
    descending score and then candidate ID for deterministic offline evaluation.
    """
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("tenant_id is required")
    if not 1 <= top_k <= 100:
        raise ValueError("top_k must be between 1 and 100")
    if isinstance(max_hops, bool) or not isinstance(max_hops, int) or not 1 <= max_hops <= MAX_GRAPH_HOPS:
        raise ValueError(f"max_hops must be between 1 and {MAX_GRAPH_HOPS}")
    if not math.isfinite(decay) or not 0 < decay <= 1:
        raise ValueError("decay must be finite and in (0, 1]")
    if len(edges) > MAX_GRAPH_EDGES:
        raise ValueError("graph edge count exceeds the configured limit")
    if len(seed_candidates) > MAX_GRAPH_SEEDS:
        raise ValueError("seed candidate count exceeds the configured limit")
    if len(entity_chunk_ids) > MAX_GRAPH_ENTITIES:
        raise ValueError("graph entity count exceeds the configured limit")
    association_count = 0
    for chunk_ids in entity_chunk_ids.values():
        if not isinstance(chunk_ids, Sequence) or isinstance(chunk_ids, (str, bytes)):
            raise TypeError("entity chunk associations must be sequences of chunk IDs")
        association_count += len(chunk_ids)
        if association_count > MAX_ENTITY_CHUNK_ASSOCIATIONS:
            raise ValueError("entity-to-chunk association count exceeds the configured limit")

    scoped_seeds: list[RankedCandidate] = []
    seen_seed_ids: set[str] = set()
    for candidate in seed_candidates:
        if not isinstance(candidate, RankedCandidate):
            raise TypeError("seed_candidates must contain RankedCandidate values")
        if candidate.score < 0:
            raise ValueError("seed candidate scores must be non-negative for graph decay")
        if candidate.candidate_id in seen_seed_ids:
            continue
        seen_seed_ids.add(candidate.candidate_id)
        if chunk_tenants.get(candidate.candidate_id) == tenant_id:
            scoped_seeds.append(candidate)

    entity_to_chunks: dict[str, tuple[str, ...]] = {}
    chunk_to_entities: dict[str, list[str]] = defaultdict(list)
    for entity_id, chunk_ids in entity_chunk_ids.items():
        if not isinstance(entity_id, str) or not entity_id.strip() or len(entity_id) > 200:
            raise ValueError("entity IDs must be non-empty strings of at most 200 characters")
        if len(chunk_ids) > MAX_CHUNKS_PER_ENTITY:
            raise ValueError("an entity has too many associated chunks")
        clean_ids: list[str] = []
        entity_is_scoped = entity_tenants.get(entity_id) == tenant_id
        for chunk_id in chunk_ids:
            if not isinstance(chunk_id, str) or not chunk_id.strip() or len(chunk_id) > 200:
                raise ValueError("chunk IDs must be non-empty strings of at most 200 characters")
            if entity_is_scoped and chunk_tenants.get(chunk_id) == tenant_id and chunk_id not in clean_ids:
                clean_ids.append(chunk_id)
                chunk_to_entities[chunk_id].append(entity_id)
                if len(chunk_to_entities[chunk_id]) > MAX_ENTITIES_PER_CHUNK:
                    raise ValueError("a chunk has too many associated entities")
        entity_to_chunks[entity_id] = tuple(clean_ids)

    adjacency: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for edge in edges:
        if not isinstance(edge, GraphEdge):
            raise TypeError("edges must contain GraphEdge values")
        if (
            edge.tenant_id != tenant_id
            or entity_tenants.get(edge.source_entity_id) != tenant_id
            or entity_tenants.get(edge.target_entity_id) != tenant_id
        ):
            continue
        adjacency[edge.source_entity_id].append((edge.target_entity_id, edge.relation_type))
        adjacency[edge.target_entity_id].append((edge.source_entity_id, edge.relation_type))
    for neighbors in adjacency.values():
        neighbors.sort(key=lambda item: (item[0], item[1]))

    best: dict[str, GraphCandidate] = {}
    for seed in scoped_seeds:
        base = GraphCandidate(seed.candidate_id, seed.score, seed.candidate_id, (), (), 0)
        previous = best.get(seed.candidate_id)
        if previous is None or base.score > previous.score:
            best[seed.candidate_id] = base

        queue: deque[tuple[str, int, tuple[str, ...], tuple[str, ...], frozenset[str]]] = deque()
        for entity_id in sorted(chunk_to_entities.get(seed.candidate_id, [])):
            queue.append((entity_id, 0, (entity_id,), (), frozenset({entity_id})))
        while queue:
            entity_id, hops, entity_path, relation_path, visited = queue.popleft()
            if hops >= max_hops:
                continue
            for neighbor_id, relation in adjacency.get(entity_id, []):
                if neighbor_id in visited:
                    continue
                next_hops = hops + 1
                next_entity_path = entity_path + (neighbor_id,)
                next_relation_path = relation_path + (relation,)
                next_score = seed.score * (decay ** next_hops)
                for chunk_id in entity_to_chunks.get(neighbor_id, ()):
                    if chunk_id == seed.candidate_id:
                        continue
                    candidate = GraphCandidate(
                        chunk_id, next_score, seed.candidate_id, next_entity_path,
                        next_relation_path, next_hops,
                    )
                    current = best.get(chunk_id)
                    if current is None or (
                        candidate.score, -candidate.hop_count, candidate.seed_candidate_id
                    ) > (
                        current.score, -current.hop_count, current.seed_candidate_id
                    ):
                        best[chunk_id] = candidate
                queue.append((
                    neighbor_id, next_hops, next_entity_path, next_relation_path,
                    visited | {neighbor_id},
                ))

    return sorted(best.values(), key=lambda item: (-item.score, item.candidate_id))[:top_k]

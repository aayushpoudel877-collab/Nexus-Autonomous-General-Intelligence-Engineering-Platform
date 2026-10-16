import pytest

import services.rag.graph_retrieval as graph_retrieval
from services.rag.graph_retrieval import (
    MAX_GRAPH_SEEDS,
    GraphEdge,
    graph_assisted_retrieve,
)
from services.rag.ranking import RankedCandidate


def _edge(source, target, tenant="org-a", relation="related_to"):
    return GraphEdge(tenant, source, target, relation)


def test_graph_expands_seed_to_related_chunks_with_explanation():
    results = graph_assisted_retrieve(
        [RankedCandidate("chunk-1", 1.0)],
        [_edge("entity-a", "entity-b", relation="authored_by")],
        {"entity-a": ["chunk-1"], "entity-b": ["chunk-2"]},
        tenant_id="org-a",
        chunk_tenants={"chunk-1": "org-a", "chunk-2": "org-a"},
        entity_tenants={"entity-a": "org-a", "entity-b": "org-a"},
    )
    assert [item.candidate_id for item in results] == ["chunk-1", "chunk-2"]
    expanded = results[1]
    assert expanded.score == pytest.approx(0.65)
    assert expanded.seed_candidate_id == "chunk-1"
    assert expanded.entity_path == ("entity-a", "entity-b")
    assert expanded.relation_path == ("authored_by",)
    assert expanded.hop_count == 1


def test_graph_never_returns_cross_tenant_chunks_or_traverses_other_tenant_edges():
    results = graph_assisted_retrieve(
        [RankedCandidate("seed", 0.9), RankedCandidate("foreign-seed", 1.0)],
        [_edge("a", "b", tenant="org-b"), _edge("a", "c", tenant="org-a")],
        {"a": ["seed", "foreign-seed"], "b": ["foreign-result"], "c": ["local-result"]},
        tenant_id="org-a",
        chunk_tenants={
            "seed": "org-a", "foreign-seed": "org-b",
            "foreign-result": "org-b", "local-result": "org-a",
        },
        entity_tenants={"a": "org-a", "b": "org-b", "c": "org-a"},
    )
    ids = {item.candidate_id for item in results}
    assert "foreign-seed" not in ids
    assert "foreign-result" not in ids
    assert "local-result" in ids


def test_multi_hop_is_bounded_and_score_decays():
    results = graph_assisted_retrieve(
        [RankedCandidate("one", 1.0)],
        [_edge("a", "b"), _edge("b", "c")],
        {"a": ["one"], "b": ["two"], "c": ["three"]},
        tenant_id="org-a",
        chunk_tenants={"one": "org-a", "two": "org-a", "three": "org-a"},
        entity_tenants={"a": "org-a", "b": "org-a", "c": "org-a"},
        max_hops=2,
        decay=0.5,
    )
    by_id = {item.candidate_id: item for item in results}
    assert by_id["two"].score == pytest.approx(0.5)
    assert by_id["three"].score == pytest.approx(0.25)
    assert by_id["three"].hop_count == 2


def test_duplicate_paths_keep_strongest_score_deterministically():
    results = graph_assisted_retrieve(
        [RankedCandidate("seed", 1.0), RankedCandidate("seed", 0.8)],
        [_edge("a", "b"), _edge("a", "c"), _edge("b", "d"), _edge("c", "d")],
        {"a": ["seed"], "b": ["b-chunk"], "c": ["c-chunk"], "d": ["target"]},
        tenant_id="org-a",
        chunk_tenants={key: "org-a" for key in ("seed", "b-chunk", "c-chunk", "target")},
        entity_tenants={key: "org-a" for key in ("a", "b", "c", "d")},
        max_hops=2,
    )
    target = next(item for item in results if item.candidate_id == "target")
    assert target.score == pytest.approx(0.65**2)
    assert target.hop_count == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        {"tenant_id": "", "top_k": 5, "max_hops": 1, "decay": 0.5},
        {"tenant_id": "org-a", "top_k": 0, "max_hops": 1, "decay": 0.5},
        {"tenant_id": "org-a", "top_k": 5, "max_hops": 3, "decay": 0.5},
        {"tenant_id": "org-a", "top_k": 5, "max_hops": 1, "decay": 0},
        {"tenant_id": "org-a", "top_k": 5, "max_hops": 1, "decay": float("nan")},
    ],
)
def test_invalid_search_bounds_are_rejected(kwargs):
    with pytest.raises(ValueError):
        graph_assisted_retrieve(
            [RankedCandidate("seed", 1.0)], [], {}, chunk_tenants={"seed": "org-a"}, entity_tenants={}, **kwargs
        )


def test_rejects_malformed_edges_and_excessive_entity_fanout():
    with pytest.raises(ValueError):
        GraphEdge("org-a", "same", "same", "related")
    with pytest.raises(ValueError, match="too many associated entities"):
        graph_assisted_retrieve(
            [RankedCandidate("seed", 1.0)], [],
            {f"entity-{i}": ["seed"] for i in range(33)},
            tenant_id="org-a", chunk_tenants={"seed": "org-a"},
            entity_tenants={f"entity-{i}": "org-a" for i in range(33)},
        )



def test_graph_rejects_negative_seed_scores_and_non_sequence_associations():
    with pytest.raises(ValueError, match="non-negative"):
        graph_assisted_retrieve(
            [RankedCandidate("seed", -0.1)],
            [],
            {},
            tenant_id="org-a",
            chunk_tenants={"seed": "org-a"},
            entity_tenants={},
        )
    with pytest.raises(TypeError, match="sequences of chunk IDs"):
        graph_assisted_retrieve(
            [RankedCandidate("seed", 1.0)],
            [],
            {"entity-a": "seed"},
            tenant_id="org-a",
            chunk_tenants={"seed": "org-a"},
            entity_tenants={"entity-a": "org-a"},
        )


def test_graph_seed_count_is_bounded_before_expansion():
    seeds = [RankedCandidate(f"seed-{index}", 1.0) for index in range(MAX_GRAPH_SEEDS + 1)]
    with pytest.raises(ValueError, match="seed candidate count"):
        graph_assisted_retrieve(
            seeds,
            [],
            {},
            tenant_id="org-a",
            chunk_tenants={item.candidate_id: "org-a" for item in seeds},
            entity_tenants={},
        )



def test_graph_entity_and_association_counts_are_bounded(monkeypatch):
    monkeypatch.setattr(graph_retrieval, "MAX_GRAPH_ENTITIES", 1)
    with pytest.raises(ValueError, match="entity count"):
        graph_assisted_retrieve(
            [],
            [],
            {"entity-a": [], "entity-b": []},
            tenant_id="org-a",
            chunk_tenants={},
            entity_tenants={},
        )

    monkeypatch.setattr(graph_retrieval, "MAX_GRAPH_ENTITIES", 10)
    monkeypatch.setattr(graph_retrieval, "MAX_ENTITY_CHUNK_ASSOCIATIONS", 2)
    with pytest.raises(ValueError, match="association count"):
        graph_assisted_retrieve(
            [],
            [],
            {"entity-a": ["one", "two"], "entity-b": ["three"]},
            tenant_id="org-a",
            chunk_tenants={},
            entity_tenants={},
        )



def test_graph_traversal_has_a_total_work_budget(monkeypatch):
    monkeypatch.setattr(graph_retrieval, "MAX_GRAPH_TRAVERSAL_STEPS", 1)
    with pytest.raises(ValueError, match="traversal step budget"):
        graph_assisted_retrieve(
            [RankedCandidate("seed", 1.0)],
            [_edge("a", "b"), _edge("a", "c")],
            {"a": ["seed"], "b": ["chunk-b"], "c": ["chunk-c"]},
            tenant_id="org-a",
            chunk_tenants={key: "org-a" for key in ("seed", "chunk-b", "chunk-c")},
            entity_tenants={key: "org-a" for key in ("a", "b", "c")},
        )

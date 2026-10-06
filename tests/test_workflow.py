import pytest

from services.api.app.db.base import Base
from services.api.app.services.workflow import (
    build_workflow_policy_snapshot,
    classify_run_after_tick,
    ensure_node_run_transition,
    ensure_run_transition,
    ready_node_keys,
    validate_workflow_graph,
)
from services.api.app.schemas.workflow import WorkflowCreate, WorkflowNodeCreate


def test_phase_22_tables_are_registered():
    assert "workflow_definitions" in Base.metadata.tables
    assert "workflow_nodes" in Base.metadata.tables
    assert "workflow_runs" in Base.metadata.tables
    assert "workflow_node_runs" in Base.metadata.tables
    assert "workflow_approvals" in Base.metadata.tables


def test_phase_22_routes_are_registered():
    from services.api.app.main import app
    paths = app.openapi()["paths"]
    assert "/api/v1/workflows" in paths
    assert "/api/v1/workflows/{workflow_id}/runs" in paths
    assert "/api/v1/workflows/{workflow_id}/runs/{run_id}/tick" in paths
    assert "/api/v1/workflows/{workflow_id}/runs/{run_id}/cancel" in paths
    assert "/api/v1/workflows/{workflow_id}/runs/{run_id}/approvals/{approval_id}" in paths


def test_workflow_graph_is_topologically_validated():
    order, depth = validate_workflow_graph([
        {"node_key": "a", "node_type": "checkpoint", "depends_on": []},
        {"node_key": "b", "node_type": "approval", "depends_on": ["a"]},
        {"node_key": "c", "node_type": "checkpoint", "depends_on": ["b"]},
    ])
    assert order == ["a", "b", "c"]
    assert depth == 3


def test_workflow_graph_rejects_cycles():
    with pytest.raises(ValueError, match="acyclic"):
        validate_workflow_graph([
            {"node_key": "a", "node_type": "checkpoint", "depends_on": ["b"]},
            {"node_key": "b", "node_type": "checkpoint", "depends_on": ["a"]},
        ])


def test_workflow_graph_rejects_unknown_dependencies():
    with pytest.raises(ValueError, match="unknown node"):
        validate_workflow_graph([{"node_key": "a", "node_type": "checkpoint", "depends_on": ["missing"]}])


def test_workflow_schema_rejects_duplicate_keys():
    with pytest.raises(ValueError, match="unique"):
        WorkflowCreate(name="Example", nodes=[
            WorkflowNodeCreate(node_key="step", title="One", node_type="checkpoint"),
            WorkflowNodeCreate(node_key="step", title="Two", node_type="checkpoint"),
        ])


def test_ready_nodes_require_all_dependencies_to_succeed():
    nodes = [
        {"node_key": "a", "depends_on": []},
        {"node_key": "b", "depends_on": ["a"]},
        {"node_key": "c", "depends_on": ["a", "b"]},
    ]
    assert ready_node_keys(nodes, {"a": "pending", "b": "pending", "c": "pending"}) == ["a"]
    assert ready_node_keys(nodes, {"a": "succeeded", "b": "pending", "c": "pending"}) == ["b"]


def test_workflow_lifecycle_is_fail_closed():
    ensure_run_transition("queued", "running")
    ensure_run_transition("running", "paused")
    ensure_run_transition("paused", "running")
    ensure_run_transition("running", "succeeded")
    with pytest.raises(ValueError):
        ensure_run_transition("succeeded", "running")
    ensure_node_run_transition("pending", "ready")
    ensure_node_run_transition("ready", "running")
    ensure_node_run_transition("running", "succeeded")


def test_workflow_policy_snapshot_is_frozen():
    snapshot = build_workflow_policy_snapshot()
    assert snapshot["version"] == 1
    assert snapshot["graph"]["max_nodes"] == 100
    assert snapshot["graph"]["require_acyclic"] is True
    assert snapshot["scheduling"]["lease_seconds"] == 120
    assert snapshot["approval"]["fail_closed"] is True


def test_run_classification_prioritizes_failure_and_approval():
    assert classify_run_after_tick({"a": "failed", "b": "succeeded"}, False) == "failed"
    assert classify_run_after_tick({"a": "succeeded", "b": "pending"}, True) == "paused"
    assert classify_run_after_tick({"a": "succeeded", "b": "succeeded"}, False) == "succeeded"
    assert classify_run_after_tick({"a": "running"}, False) == "running"

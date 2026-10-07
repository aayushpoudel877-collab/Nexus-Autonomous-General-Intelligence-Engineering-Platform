"""Pure workflow graph and lifecycle rules for durable orchestration."""

from collections import defaultdict, deque


_NODE_TYPES = {"checkpoint", "research_task", "execution", "approval"}
_RUN_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"running", "cancelled"},
    "running": {"paused", "succeeded", "failed", "cancelled"},
    "paused": {"running", "cancelled", "failed"},
    "succeeded": set(),
    "failed": {"running"},
    "cancelled": set(),
}
_NODE_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"ready", "cancelled"},
    "ready": {"running", "failed", "cancelled"},
    "running": {"succeeded", "failed", "blocked", "cancelled", "retry_waiting"},
    "blocked": {"ready", "cancelled"},
    "failed": {"ready", "cancelled"},
    "retry_waiting": {"pending", "cancelled"},
    "succeeded": set(),
    "cancelled": set(),
}


def ensure_run_transition(current: str, requested: str) -> None:
    if requested == current:
        return
    if requested not in _RUN_TRANSITIONS.get(current, set()):
        raise ValueError(f"Cannot change workflow run status from '{current}' to '{requested}'")


def ensure_node_run_transition(current: str, requested: str) -> None:
    if requested == current:
        return
    if requested not in _NODE_TRANSITIONS.get(current, set()):
        raise ValueError(f"Cannot change workflow node status from '{current}' to '{requested}'")


def validate_workflow_graph(nodes: list[dict]) -> tuple[list[str], int]:
    if not 1 <= len(nodes) <= 100:
        raise ValueError("A workflow must contain between 1 and 100 nodes")
    keys = [str(node.get("node_key", "")) for node in nodes]
    if any(not key for key in keys):
        raise ValueError("Every workflow node must have a key")
    if len(keys) != len(set(keys)):
        raise ValueError("Workflow node keys must be unique")
    node_map = {key: node for key, node in zip(keys, nodes, strict=True)}
    indegree = {key: 0 for key in keys}
    edges: dict[str, list[str]] = defaultdict(list)
    for key, node in node_map.items():
        node_type = node.get("node_type")
        if node_type not in _NODE_TYPES:
            raise ValueError(f"Unsupported workflow node type: {node_type}")
        deps = node.get("depends_on", []) or []
        if len(deps) != len(set(deps)):
            raise ValueError(f"Node '{key}' lists a dependency more than once")
        if key in deps:
            raise ValueError(f"Node '{key}' cannot depend on itself")
        for dep in deps:
            if dep not in node_map:
                raise ValueError(f"Node '{key}' depends on unknown node '{dep}'")
            edges[dep].append(key)
            indegree[key] += 1

    queue = deque(key for key, degree in indegree.items() if degree == 0)
    order: list[str] = []
    depth = {key: 1 for key in queue}
    while queue:
        key = queue.popleft()
        order.append(key)
        for child in edges[key]:
            depth[child] = max(depth.get(child, 1), depth[key] + 1)
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(order) != len(keys):
        raise ValueError("Workflow graph must be acyclic")
    max_depth = max(depth.values(), default=0)
    if max_depth > 50:
        raise ValueError("Workflow graph depth cannot exceed 50 nodes")
    return order, max_depth


def ready_node_keys(nodes: list[dict], node_status: dict[str, str]) -> list[str]:
    ready: list[str] = []
    for node in nodes:
        key = node["node_key"]
        if node_status.get(key, "pending") != "pending":
            continue
        if all(node_status.get(dep) == "succeeded" for dep in node.get("depends_on", [])):
            ready.append(key)
    return ready


def classify_run_after_tick(node_status: dict[str, str], approval_pending: bool) -> str:
    statuses = list(node_status.values())
    if any(status == "failed" for status in statuses):
        return "failed"
    if approval_pending:
        return "paused"
    if statuses and all(status == "succeeded" for status in statuses):
        return "succeeded"
    return "running"


def build_workflow_policy_snapshot(*, version: int = 1, max_nodes: int = 100, max_depth: int = 50) -> dict:
    if version != 1:
        raise ValueError("Unsupported workflow policy version")
    return {
        "version": version,
        "graph": {"max_nodes": max_nodes, "max_depth": max_depth, "require_acyclic": True},
        "scheduling": {"mode": "durable_tick", "max_parallel_nodes": 8, "lease_seconds": 120},
        "approval": {"mode": "human_gate", "fail_closed": True},
        "provenance": {"policy_frozen_at_start": True},
    }

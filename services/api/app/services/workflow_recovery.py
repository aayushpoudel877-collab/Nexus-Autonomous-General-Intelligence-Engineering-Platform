"""Generate a conservative, read-only recovery plan from workflow replay evidence."""

from __future__ import annotations

from dataclasses import dataclass


RECOVERABLE_NODE_STATES = {"failed", "retry_waiting", "pending"}
TERMINAL_RUN_STATES = {"succeeded", "cancelled"}
ALLOWED_ACTIONS = {"inspect", "retry_node", "resume_run", "manual_review"}


@dataclass(frozen=True)
class RecoveryAction:
    action: str
    node_key: str | None
    reason: str
    requires_approval: bool = True


@dataclass(frozen=True)
class RecoveryPlan:
    run_status: str
    replay_drifted: bool
    actions: tuple[RecoveryAction, ...]
    automatic_mutation_allowed: bool = False


def build_recovery_plan(
    *,
    run_status: str,
    node_statuses: dict[str, str],
    replay_drifted: bool,
    max_actions: int = 25,
) -> RecoveryPlan:
    """Recommend bounded actions; never execute or authorize state changes."""
    if max_actions < 1 or max_actions > 100:
        raise ValueError("max_actions must be between 1 and 100")
    actions: list[RecoveryAction] = []
    if replay_drifted:
        actions.append(
            RecoveryAction(
                action="inspect",
                node_key=None,
                reason="Live workflow state differs from its event-journal projection.",
            )
        )
    if run_status in TERMINAL_RUN_STATES:
        actions.append(
            RecoveryAction(
                action="manual_review",
                node_key=None,
                reason="Terminal runs are not automatically reopened by recovery planning.",
            )
        )
    else:
        for key, status in sorted(node_statuses.items()):
            if status == "failed":
                actions.append(
                    RecoveryAction(
                        action="retry_node",
                        node_key=key,
                        reason="Node failed; verify retry policy, side effects, and attempt budget first.",
                    )
                )
            elif status == "retry_waiting":
                actions.append(
                    RecoveryAction(
                        action="resume_run",
                        node_key=key,
                        reason="A durable retry is waiting; let the normal scheduler enforce its due time.",
                    )
                )
        if not actions:
            actions.append(
                RecoveryAction(
                    action="manual_review",
                    node_key=None,
                    reason="No safe recovery recommendation can be inferred from current evidence.",
                )
            )
    return RecoveryPlan(
        run_status=run_status,
        replay_drifted=replay_drifted,
        actions=tuple(actions[:max_actions]),
    )

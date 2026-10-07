# Orchestrator

Coordinates durable workflows across research and controlled execution boundaries.

## Phase 22

The orchestrator is now a standalone worker-backed runtime. services/orchestrator/engine.py owns workflow tick semantics and is shared by the authenticated API and background worker. services/orchestrator/worker.py claims queued or owned/expired running workflow records with PostgreSQL row locks and finite leases, then delegates state transitions to the shared engine.

The worker may observe research-task and controlled-execution state, advance checkpoints, create approval gates, and recover abandoned workflow leases. It cannot execute arbitrary plugin code or bypass the execution service artifact, sandbox, egress, or secret controls.

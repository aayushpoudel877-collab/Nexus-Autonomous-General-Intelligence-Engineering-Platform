# Durable Autonomous Workflows

## Phase 22 boundary

Phase 22 adds a durable, tenant-scoped workflow control plane for coordinating research tasks, existing controlled execution requests, checkpoints, and human approval gates.

A workflow is a versioned graph. Node keys are stable within a definition and dependencies are explicit. The graph validator rejects duplicate keys, missing dependencies, self-dependencies, unsupported node types, cycles, and graphs deeper than 50 nodes.

## Runtime state

A workflow run starts in `queued` and is claimed by the dedicated orchestrator worker. PostgreSQL row locks prevent two workers from claiming the same row concurrently. The run stores a worker identity, attempt count, heartbeat and expiring lease. If a worker disappears, another worker may reclaim the run after lease expiry.

Each node has a durable node-run record with status, attempt number, lease, input, output and terminal error. `checkpoint` nodes complete locally. `research_task` nodes wait on an existing same-organization research task. `execution` nodes wait on an existing same-organization controlled execution request. They never bypass the execution API, artifact trust, sandbox, egress or secret gates. `approval` nodes create a human approval record and pause the run until an owner/admin decides.

## Safety rules

The workflow layer does not execute arbitrary code, dereference remote URLs, resolve credentials, or create privileged execution requests. It only coordinates already-governed records and propagates their terminal state. External references are resolved by ID inside the owning organization, and missing or invalid references fail closed.

The policy snapshot freezes scheduling and approval behavior at run creation. Audit events record creation, queueing, ticks, cancellations and approval decisions without persisting secret values.

## Worker contract

The standalone `services.orchestrator.worker` process claims `queued` or owned/expired `running` runs in bounded batches. A separate service container is included in the development compose file. Worker poll, lease and batch sizes are configurable through environment variables.

## API surface

- `GET /api/v1/workflows`
- `POST /api/v1/workflows`
- `GET /api/v1/workflows/{workflow_id}`
- `POST /api/v1/workflows/{workflow_id}/runs`
- `GET /api/v1/workflows/{workflow_id}/runs`
- `POST /api/v1/workflows/{workflow_id}/runs/{run_id}/tick`
- `POST /api/v1/workflows/{workflow_id}/runs/{run_id}/cancel`
- `POST /api/v1/workflows/{workflow_id}/runs/{run_id}/approvals/{approval_id}`

## Example node configuration

A research node uses `{ "research_task_id": "<uuid>" }` and an execution node uses `{ "execution_request_id": "<uuid>" }`. An approval node uses `{ "prompt": "Review the benchmark evidence before continuing." }`. Checkpoints use an empty configuration object.

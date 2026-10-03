# Controlled Execution Worker

Phase 13 introduces the first worker process behind the Phase 12 execution queue.

## Worker responsibilities

- claims queued requests with PostgreSQL row locks so multiple workers do not take the same request;
- assigns a bounded lease and heartbeats while work is active;
- requeues abandoned attempts until the retry limit, then records a terminal failure;
- respects API cancellation by requiring worker ownership before completion;
- records bounded JSON results and worker audit events.

## Runtime safety boundary

The worker is deliberately fail-closed for external plugin entrypoints. Phase 13 does not:

- download or unpack plugin packages;
- verify package signatures against configured trust roots;
- import or execute arbitrary plugin code;
- resolve external secrets;
- create outbound network connections;
- provide a container/process sandbox.

An unsupported execution is therefore recorded as `failed` with `executor_unavailable` instead of executing outside the approved boundary.

## Local development

The Docker Compose stack now includes a `worker` service. It waits for PostgreSQL and API startup, then runs:

`python -m services.execution.worker`

Worker tuning is controlled by:

- `NEXUS_WORKER_POLL_SECONDS` (default 2 seconds)
- `NEXUS_WORKER_LEASE_SECONDS` (default 60 seconds)
- `NEXUS_WORKER_ID` (defaults to the container hostname)

The next runtime phase can replace the fail-closed executor with a verified artifact adapter and isolated sandbox without changing the queue contract.

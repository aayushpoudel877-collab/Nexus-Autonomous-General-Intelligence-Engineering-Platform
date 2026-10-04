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

Phase 15 now adds shared content-addressed artifact staging and sandbox admission. The worker re-hashes staged bytes before admission and compiles a digest-pinned OCI policy without launching external plugin code. The next runtime phase can enable a dedicated launcher while keeping the queue contract unchanged.


## Phase 15 runtime admission

Verified artifacts are stored at:

`<artifact_root>/<sha256[0:2]>/<sha256[2:4]>/<sha256>`

The API and worker share the same storage volume in the local Compose stack. The worker treats the execution policy's frozen package digest and storage key as the authoritative identity and re-verifies bytes before any sandbox admission.

The sandbox command builder requires:

- an OCI image pinned by `@sha256:<digest>`;
- `--network=none`;
- read-only root filesystem;
- all Linux capabilities dropped;
- `no-new-privileges`;
- bounded memory and process count;
- a read-only artifact bind mount;
- an isolated, non-executable temporary filesystem.

Phase 15 intentionally stops at admission/command construction. The worker does not invoke the generated Docker command.

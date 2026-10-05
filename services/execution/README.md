# Controlled Execution Worker

The worker process sits behind the Phase 12 execution queue and owns the runtime boundary outside the API process.

## Worker responsibilities

- claims queued requests with PostgreSQL row locks so multiple workers do not take the same request;
- assigns a bounded lease and heartbeats while work is active;
- requeues abandoned attempts until the retry limit, then records a terminal failure;
- respects API cancellation by requiring worker ownership before completion;
- records bounded JSON results and worker audit events.

## Runtime safety boundary

External plugin execution remains governed by the Phase 14 trust and Phase 15 admission gates. Phase 16 adds an opt-in launcher, but the default worker configuration still does not execute plugin code.

The worker remains fail-closed when artifact verification, sandbox configuration, runtime availability or execution-policy checks fail.

## Local development

The Docker Compose stack includes a `worker` service. It waits for PostgreSQL and API startup, then runs:

`python -m services.execution.worker`

Worker tuning is controlled by:

- `NEXUS_WORKER_POLL_SECONDS` (default 2 seconds)
- `NEXUS_WORKER_LEASE_SECONDS` (default 60 seconds)
- `NEXUS_WORKER_ID` (defaults to a unique hostname-derived ID)
- `NEXUS_ARTIFACT_ROOT` (default `/var/lib/nexus/artifacts`)
- `NEXUS_RUNTIME_ROOT` (default `/var/lib/nexus/runtime`)
- `NEXUS_SANDBOX_IMAGE` (empty by default)
- `NEXUS_SANDBOX_LAUNCH_ENABLED` (false by default)
- `NEXUS_DOCKER_BINARY` (default `docker`)
- `NEXUS_SANDBOX_STOP_GRACE_SECONDS` (default 3 seconds)
- `NEXUS_SANDBOX_CANCELLATION_POLL_SECONDS` (default 0.5 seconds)

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

## Phase 16 isolated launcher

The worker can optionally launch the prepared OCI command when `NEXUS_SANDBOX_LAUNCH_ENABLED=true`.

Launcher controls include:

- no shell interpolation; Docker/OCI commands use an argument vector;
- image must remain pinned by SHA-256;
- networking stays disabled;
- execution timeout comes from the request policy;
- stdout/stderr are bounded before persistence;
- the launcher starts a fresh process session;
- timeout/output-limit paths terminate the process group and attempt container cleanup using the recorded container ID;
- non-zero exits, timeout and output-limit conditions are recorded as distinct terminal errors.

The default remains disabled. The local Compose worker has no Docker socket mounted and therefore remains a preparation-only worker unless an operator supplies a separate isolated runtime boundary.

## Phase 17 cooperative cancellation

A running sandbox receives a bounded cancellation poll from the worker. When the authoritative execution request changes to cancelled, the launcher:

1. stops the sandbox process group;
2. waits for the configured grace period;
3. forces termination when necessary;
4. attempts docker rm -f using the recorded container ID; and
5. returns a distinct sandbox_cancelled execution outcome.

The worker checks the persisted request state before committing its final outcome. If the API already cancelled the request, the worker records execution.worker_cancelled rather than overwriting the cancellation with a late success/failure.

Network-enabled requests remain fail-closed until the Phase 18 egress mediation boundary is active.

## Phase 18 mediated egress

Network-enabled execution is eligible only when the request uses policy version 3, declares the `network.http` capability, and contains the Phase 18 `unix_socket_broker` egress mode.

The plugin container still uses `--network=none`. For an allowlisted execution the worker creates:

- a short-lived Unix socket at the execution runtime path;
- a random per-execution token file;
- a short-lived broker subprocess, started without control-plane environment secrets, that performs the actual outbound HTTP(S) request.

The sandbox receives the socket and token as read-only mounts plus:

- `NEXUS_EGRESS_SOCKET=/nexus/egress.sock`
- `NEXUS_EGRESS_TOKEN_FILE=/nexus/egress.token`

The broker contract is JSON Lines:

`{"token":"...","method":"GET","url":"https://api.example.com/path","headers":{...},"body_base64":"..."}`

Successful responses include status code, bounded headers, base64 response bytes and a truncation flag. Redirects are not followed. The broker rejects IP-literal destinations and any DNS result that is not globally routable.

Limits are frozen into the execution policy snapshot: 128 KiB request payload, 4 MiB response body, at most four concurrent broker requests, and a maximum 15-second broker request timeout.

Direct socket access, arbitrary protocols and network namespace attachment remain unavailable.

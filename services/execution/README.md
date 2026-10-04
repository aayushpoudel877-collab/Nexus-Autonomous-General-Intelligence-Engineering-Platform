[object Object]

## Phase 16 isolated launcher

The worker can optionally launch the prepared OCI command when NEXUS_SANDBOX_LAUNCH_ENABLED=true.

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

A running sandbox now receives a bounded cancellation poll from the worker. When the authoritative execution request changes to cancelled, the launcher:

1. stops the sandbox process group;
2. waits for the configured grace period;
3. forces termination when necessary;
4. attempts docker rm -f using the recorded container ID; and
5. returns a distinct sandbox_cancelled execution outcome.

The worker checks the persisted request state before committing its final outcome. If the API already cancelled the request, the worker records execution.worker_cancelled rather than overwriting the cancellation with a late success/failure.

Configuration:

- NEXUS_SANDBOX_CANCELLATION_POLL_SECONDS (default 0.5 seconds)
- NEXUS_SANDBOX_STOP_GRACE_SECONDS (default 3 seconds)

Network-enabled requests remain fail-closed until a dedicated egress mediation boundary is implemented.

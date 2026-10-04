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

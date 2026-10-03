# Controlled Execution Boundary

Phase 12 introduces a persistent execution control plane without executing arbitrary plugin code inside the API process.

The API creates execution requests only for plugin installations that are:

1. active,
2. tied to a verified plugin release,
3. approved for the current organization,
4. granted the requested capabilities.

Each request captures bounded resource limits, network policy, input metadata, idempotency, and an immutable policy snapshot.

A future worker may consume queued requests only after adding process/container isolation, artifact verification, signed trust roots, secret-manager mediation, egress controls, CPU/memory/file-size enforcement, timeout enforcement, and execution telemetry.

The current phase intentionally stops before invoking arbitrary code.

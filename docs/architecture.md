# NEXUS-Ω Architecture

## Layers
1. **Experience** — public website, authenticated web app, LMS and admin consoles.
2. **Application** — APIs and domain services for identity, learning, projects, experiments and operations.
3. **Intelligence** — agent runtime, model adapters, retrieval, memory, evaluation and multimodal capabilities.
4. **Autonomy** — planning, execution graphs, research workflows and controlled improvement loops.
5. **Data** — relational state, object storage, vector indexes, events and experiment artifacts.
6. **Operations** — observability, security, CI/CD, policy controls and deployment automation.

## Principles
- Explicit service contracts and replaceable providers.
- Observable autonomous state transitions.
- Reproducible experiments and versioned artifacts.
- Human approval gates for consequential external actions.
- Security and evaluation are first-class platform concerns.

## ML lifecycle boundary

The Phase 6 API records training-run metadata and state, versioned model records, and evaluation results. It never imports or executes user-supplied code and never dereferences artifact URIs. Model approval is a separate, explicit state transition that requires a passed evaluation and a human review note. A later execution service must add isolated workers, resource budgets, signed artifacts, provenance, policy enforcement, and deployment approval before running training or serving models.


## Multimodal asset boundary

The multimodal service stores asset references and bounded descriptive metadata within the owning workbench project's organization. It never dereferences source references or downloads user-provided URLs, so registering a manifest cannot trigger server-side requests. The current phase does not store binary payloads, decode media, or execute inference. A future ingestion worker must use controlled storage adapters, checksum verification, file-size and decoder limits, content-type inspection, and isolation before handling bytes.


## Continuous-improvement boundary

Phase 8 records baseline/candidate comparisons only when both registered models belong to the same authorized workbench project and are not archived. Metric deltas are calculated server-side against explicit maximize/minimize thresholds. Metrics are caller-reported; a passing record means only that the submitted numbers satisfy the recorded criteria, not that a benchmark runner independently produced or verified them. Automated benchmark execution, data split controls, reproducible environment capture, proposal execution, and deployment remain future work.


## Phase 9 hardening boundary

The API now adds correlation IDs and baseline response security headers, validates production CORS/host configuration, enforces trusted hosts, exposes a database-backed readiness probe, rejects untrusted browser Origins on state-changing requests, marks authentication responses no-store, and provides a tenant-scoped audit stream. This does not by itself provide a reverse proxy, TLS termination, distributed rate limiting, secret rotation service, object-storage disaster recovery, or full tracing backend.


## Developer ecosystem boundary

Phase 10 introduces tenant-scoped developer API keys, explicit capability scopes, plugin registration metadata, and a lightweight SDK transport boundary. API keys are stored as one-way SHA-256 digests and can expire or be revoked. Plugin registrations are metadata only: the API never downloads, imports, or executes plugin packages. A future integration plane must add signed manifests, package provenance, sandboxed execution, secret management, outbound delivery controls, rate limits and policy enforcement before external plugins can run.

## Phase 11 governance boundary

The ecosystem governance layer introduces three controls before any future plugin or integration execution: external secret references instead of raw credentials, release-level package/manifest digest and signature metadata with explicit review state, and tenant-scoped installation requests with human approval and capability subset approval. Phase 11 does not download artifacts, verify trust roots automatically, execute plugin code, or make outbound network calls.


## Phase 12 controlled execution boundary

Phase 12 adds a persistent execution control plane between approved plugin installations and any future worker runtime. Execution requests are tenant-scoped and idempotent, require an approved installation tied to a verified release, and can request only capabilities already approved for that installation and declared by the plugin manifest. Resource limits and network policy are captured in a policy snapshot at request time. The API does not execute plugin code; a future worker must run outside the API process with sandboxing, artifact verification, secret mediation, egress restrictions and resource isolation.


## Phase 13 execution worker boundary

Phase 13 moves queue ownership outside the API process. Dedicated workers claim queued executions with PostgreSQL row locks and expiring leases, heartbeat active requests, recover abandoned attempts and write bounded terminal results. Cancellation clears the lease so a worker cannot later overwrite a cancelled request. Worker audit events record claims, terminal completion and lease loss without exposing request payloads.

The worker still fails closed for external plugin entrypoints. It does not fetch packages, import plugin code, resolve secrets, open outbound sockets or bypass the request's policy snapshot. The next runtime phase must provide verified artifact retrieval, signed trust roots, process/container sandboxing, resource enforcement and egress mediation before arbitrary plugin code is eligible to run.


## Phase 14 artifact trust boundary

Phase 14 adds tenant-owned Ed25519 trust roots and a detached-signature verification gate for plugin artifacts. A release is installable only after the supplied artifact bytes hash to the release package SHA-256 and the digest is validated by the release's declared signer against an active tenant trust root. Human release approval remains a separate gate. Revoking the trust root blocks new installation approval and execution for releases tied to that key.

The verification endpoint accepts bounded artifact bytes for explicit verification but does not unpack or execute them. The platform still does not retrieve arbitrary `artifact_uri` values, dereference remote URLs, resolve secrets, or launch plugin code. Those operations remain the responsibility of a future isolated sandbox runtime with egress enforcement and resource limits.


## Phase 15 runtime admission boundary

Phase 15 adds a shared, content-addressed artifact store. A cryptographically verified release is staged under its SHA-256 digest; the storage key, byte size and staging timestamp are frozen into execution provenance. Workers re-read and re-hash the artifact before admission, preventing a mutable file from silently replacing the verified payload.

The sandbox adapter compiles an OCI command only when the runtime image is pinned by SHA-256. The compiled policy requires no network, a read-only root filesystem, all Linux capabilities dropped, no-new-privileges, bounded memory and process count, a read-only artifact mount, and an isolated temporary filesystem. The adapter does not invoke the command yet, keeping plugin code outside the current worker process until end-to-end runtime controls are available.


## Phase 16 isolated launcher boundary

Phase 16 adds an opt-in isolated launcher behind the Phase 15 admission contract. The launcher invokes the configured OCI runtime with argument vectors only, never through a shell. Each invocation uses a fresh process session, a bounded request timeout, bounded stdout/stderr capture, explicit process-group termination, and container-ID cleanup for timeout or output-limit termination.

The launcher treats the execution policy as authoritative: the image is digest-pinned, the artifact is read-only, networking remains disabled, and the request timeout becomes the runtime deadline. The launcher returns structured terminal classification rather than exposing raw process internals to the API.

Launch is disabled by default. The repository's local Compose worker deliberately does not mount the Docker socket or enable launch. A deployment that enables it must supply an isolated runtime host boundary and ensure the configured artifact path is visible to that runtime.


## Phase 17 runtime cancellation boundary

Phase 17 closes the cancellation gap between the API control plane and the sandbox runtime. When an execution is marked cancelled, the worker polls the authoritative execution row during sandbox execution and terminates the sandbox process group rather than waiting for the original runtime timeout.

The launcher treats cancellation as a first-class terminal control signal and attempts container cleanup using the existing CID file. The worker then reconciles the final database state before emitting its completion audit event, so a cancelled request cannot be overwritten by a late sandbox result or lease completion.

Network-enabled execution remains blocked by the Phase 15 admission policy; the dedicated egress mediation phase must establish a controlled network boundary before allowlisted network requests can execute.

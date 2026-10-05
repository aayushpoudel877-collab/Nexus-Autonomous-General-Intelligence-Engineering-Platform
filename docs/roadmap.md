# Long-Horizon Roadmap

## Phase 0 — Foundation
Repository structure, contracts, local infrastructure, health APIs and web shell.

## Phase 1 — Identity & Core Platform
Authentication, authorization, tenancy, persistence, refresh-session management, audit events, migrations and the authenticated web workspace. Implemented in v0.2.0.

## Phase 2 — LMS
Course authoring, modules, lessons, enrollment, progress tracking, assessments, grading, learner dashboard and PostgreSQL migrations. Implemented in v0.2.0.

## Phase 3 — AI Tutor
Authenticated persistent conversations, course-aware lesson context, provider boundary with explicit local fallback, bounded context, ownership/tenant checks and migration. Initial implementation in v0.3.0. Hosted-model adapter, retrieval indexing, evaluation and usage budgets remain future work.

## Phase 4 — AI Engineering Workbench
Initial implementation: tenant-scoped project creation/listing, dataset metadata, experiment planning/status tracking, validated API schemas, persistence migration, and web workspace. Model registry, artifact storage, evaluation execution and reproducibility bundles remain future work.

## Phase 5 — Autonomous Research
Initial implementation: tenant-scoped research plans, task dependency validation, explicit task lifecycle transitions, prerequisite-aware execution status, output summaries and a research planner UI. Autonomous tool execution, literature retrieval and data-collection integrations remain future work.

## Phase 6 — Autonomous ML Lifecycle
Initial implementation: tenant-scoped training-run metadata and lifecycle transitions, model registry records linked only to successful same-project runs or experiments, evaluation records, immutable terminal states, unique model versioning, and a human-review note plus passing-evaluation gate before model approval. This phase tracks lifecycle state; it does not execute training code, load artifact URIs, deploy models, or monitor live endpoints.

## Phase 7 — Multimodal Intelligence
Initial implementation: tenant-scoped asset manifests for text, image, audio, video and structured data; modality-aware MIME and metadata validation; optional SHA-256, size, duration and dimensions; API and catalog UI. This is a metadata-only manifest layer. Upload/storage adapters, content decoding, feature extraction, modality-specific inference, dataset-level split management and automated cross-modal benchmarks remain future work.

## Phase 8 — Continuous Improvement
Initial implementation: tenant-scoped baseline/candidate model comparisons, bounded metric payloads, directional improvement thresholds, recorded deltas, regression explanations, comparison history and a project-scoped UI. Submitted metrics are caller-reported evidence: this phase does not execute models, independently verify benchmark results, automatically generate experiments, or apply model changes.

## Phase 9 — Production Hardening
Initial implementation: explicit multi-organization selection, deterministic threshold evaluation, production CORS/host validation, trusted-host enforcement, request correlation IDs, baseline API security headers, database-backed readiness checks, request-correlated audit events and an authorized audit stream UI. Distributed rate limiting, secret rotation, full tracing/metrics, disaster recovery automation, governance policies and cost controls remain future work.

## Phase 10 — Ecosystem
Initial implementation: tenant-scoped API keys with explicit scopes, metadata-only plugin registration, API-key authentication, audit coverage for developer administration, and a lightweight Python SDK. Plugin execution, package retrieval, outbound webhooks, multi-language SDK generation and full integration marketplace controls remain future work.

## Phase 11 — Governed Integrations & Plugin Supply Chain
Initial implementation: tenant-scoped integration connections that store only non-secret configuration plus external secret references; plugin release metadata with package/manifest digests and review state; verified-release installation requests; explicit owner/admin approval; capability subset approval; and audit coverage. Artifact download, signature trust-root automation, sandboxed execution, outbound network dispatch, webhook delivery and secret-manager adapters remain future work.

## Phase 12 — Controlled Execution Plane
Initial implementation: tenant-scoped, idempotent execution requests linked to approved plugin installations; capability subset enforcement against the installation and plugin manifest; bounded timeout, memory and output limits; explicit network policy; reproducible policy snapshots; cancellation; and a persistent queue boundary. Arbitrary plugin execution, worker sandboxing, package fetching, secret-manager resolution and outbound network dispatch remain future work.


## Phase 13 — Execution Worker & Lease Control
Initial implementation: a separate execution worker process with PostgreSQL row-lock claiming, bounded leases, heartbeats, retry/recovery for abandoned work, cancellation-safe completion, bounded result records and worker audit events. The worker intentionally fails closed for external plugin entrypoints because artifact retrieval, trust-root verification, secret mediation, egress enforcement and sandboxed plugin execution are not yet activated.


## Phase 14 — Cryptographic Artifact Trust
Initial implementation: tenant-scoped Ed25519 trust roots, signed artifact verification against the release SHA-256, explicit verification metadata, trust-root revocation, and installation/execution gates that require both human release approval and a currently active verification root. Artifact bytes are verified only when explicitly supplied to the verification endpoint; the platform still does not fetch packages from arbitrary URIs, unpack them, execute them, resolve secrets, or bypass the worker sandbox boundary.


## Phase 15 — Artifact Staging & Sandbox Admission
Initial implementation: verified plugin artifacts are durably stored in a content-addressed filesystem, their storage identity and size are frozen into execution provenance, and workers perform integrity-checked artifact admission before runtime launch. A digest-pinned OCI sandbox command builder enforces no network, read-only root filesystem, dropped Linux capabilities, no-new-privileges, process and memory bounds, and read-only artifact mounts. Phase 15 still does not launch arbitrary plugin code; the next runtime phase must add an explicitly enabled isolated launcher and enforce execution timeout, output capture and egress mediation end-to-end.


## Phase 16 — Opt-in Isolated Sandbox Launcher
Initial implementation: a dedicated launcher executes only digest-pinned OCI commands, never through a shell. The launcher uses a new process session, bounded runtime timeout, bounded stdout/stderr capture, explicit process-group termination, container-ID cleanup on timeout/output overflow, and deterministic result classification. Launching remains opt-in and disabled by default; the worker container does not mount the Docker socket, so deployment must explicitly provide an isolated runtime boundary before enabling it.


## Phase 17 — Cooperative Runtime Cancellation & Reconciliation
Initial implementation: running sandbox executions now poll the authoritative execution record for cancellation, terminate the sandbox process group, remove the active container when possible, and classify cancellation separately from timeout and output-limit failures. Worker completion reconciles against the current database state so a request cancelled by the API cannot be overwritten by a late runtime result. Cancellation polling is bounded and configurable. Network-enabled execution remains fail-closed pending a dedicated egress mediation phase.


## Phase 18 — Controlled Egress Mediation
Initial implementation: allowlisted HTTP(S) execution is mediated through a per-execution authenticated Unix-socket broker while the plugin sandbox remains on `--network=none`. The broker validates exact host/port allowlists, resolves destinations and rejects non-public addresses, pins connections to the resolved IP with TLS hostname verification, disables redirects, bounds request/response sizes and request concurrency, and cleans up its socket/token at execution end. Network-enabled execution also requires the explicit `network.http` capability. Direct network access from the sandbox remains impossible by design.

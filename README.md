# NEXUS-Ω — Autonomous General Intelligence Engineering Platform

NEXUS-Ω is a production-oriented, research-driven platform for building autonomous AI systems, AI-assisted software engineering, learning experiences, and intelligent orchestration.

## Product scope

The long-term platform combines:

- AI/ML and multimodal intelligence
- autonomous research and engineering workflows
- AI tutoring and intelligent learning
- Learning Management System (LMS)
- AI-powered LMS intelligence
- backend APIs and persistent data
- identity, tenancy, RBAC and auditability
- web application and operator control plane
- testing, observability and deployment infrastructure

The platform is designed to evolve through measurable research and engineering loops while keeping humans in control of consequential actions.

## Initial architecture

- **apps/web** — Next.js user-facing web application and LMS
- **services/api** — FastAPI application and API contracts
- **services/orchestrator** — autonomous workflow orchestration
- **services/ai-core** — model/provider abstraction and agent runtime foundations
- **services/learning** — LMS domain services
- **packages/shared** — shared Python domain contracts
- **infra** — local and deployment infrastructure
- **docs** — architecture and engineering documentation

## Development

The repository is intentionally structured as a monorepo so the platform can grow across multiple engineering teams without coupling every subsystem.

See `docs/architecture.md` and `docs/roadmap.md` for the system boundaries and staged delivery plan.

## Current implementation status

- **Phase 1 — Identity:** authentication, refresh sessions, roles, organization membership and audit events. Ambiguous multi-organization membership now fails closed until an explicit organization selector is implemented.
- **Phase 2 — LMS:** course authoring, modules, lessons, enrollment, progress tracking, assessments, grading and PostgreSQL migrations. Progress updates and assessment submissions are scoped to the active organization.
- **Phase 3 — AI Tutor:** persisted conversations and course lesson context with a clearly disclosed local fallback. A hosted language-model adapter is not yet connected.
- **Phase 4 — AI Engineering Workbench:** project and dataset metadata, experiment planning and lifecycle tracking.
- **Phase 5 — Autonomous Research (initial):** research plans, dependency-aware tasks, lifecycle validation and output summaries.
- **Phase 6 — Autonomous ML Lifecycle (initial):** tenant-scoped training-run tracking, versioned model registry metadata, numeric evaluation thresholds, terminal-record immutability, and a human-note gate before model approval.
- **Phase 7 — Multimodal Intelligence (initial):** tenant-scoped asset manifests for text, image, audio, video and structured data, modality-aware metadata validation, optional SHA-256 and size/duration/dimension fields, and a catalog UI.
- **Phase 8 — Continuous Improvement (initial):** tenant-scoped baseline/candidate model comparisons, bounded metric payloads, directional improvement thresholds, recorded deltas, regression explanations and comparison history.
- **Phase 9 — Production Hardening (initial):** explicit organization selection, request correlation, trusted-host/security-header handling, database readiness checks, request-correlated audit events, state-changing Origin checks, authentication no-store responses and bounded request bodies.
- **Phase 10 — Developer Ecosystem (initial):** tenant-scoped developer API keys with explicit scopes, metadata-only plugin registration, scoped API-key authentication, audit coverage for key/plugin administration, and a dependency-free Python SDK. Plugin execution, package retrieval and outbound integrations remain future work.

The research planner currently tracks plans and tasks; it does not autonomously run external tools or collect data. The ML lifecycle tracks training-run metadata and model records, and now includes a deterministic server-side threshold evaluator; the evaluator validates submitted metrics against explicit criteria but does not execute or independently measure a model. The multimodal catalog records references and metadata only; it does not upload, fetch, decode or infer on asset content. Phase 9 adds explicit organization selection, request correlation, trusted-host/security-header handling, database readiness checks and an authorized audit-event stream. Full distributed rate limiting, tracing, secret rotation, disaster recovery and byte-level multimodal processing remain future work.

- **Phase 13 — Execution Worker & Lease Control:** a separate worker process now claims queued executions with PostgreSQL row locks, bounded leases and heartbeats, recovers abandoned attempts, preserves cancellation races, records bounded results and emits worker audit events. External plugin package execution remains blocked until a verified artifact sandbox is introduced.

- **Phase 14 — Cryptographic Artifact Trust:** tenant-owned Ed25519 trust roots, bounded detached-signature verification against release SHA-256, human release approval after cryptographic verification, and revocation-aware installation/execution gates. The platform still does not fetch or execute arbitrary plugin packages.

- **Phase 15 — Artifact Staging & Sandbox Admission:** verified releases are stored by immutable SHA-256 identity, worker provenance freezes the staged artifact, and the worker compiles a digest-pinned, no-network OCI sandbox policy without launching arbitrary plugin code.

- **Phase 16 — Opt-in Isolated Sandbox Launcher:** verified executions can optionally invoke a digest-pinned OCI sandbox with no shell, no network, bounded output, hard timeout and container cleanup. Launch remains disabled by default.

- **Phase 17 — Cooperative Runtime Cancellation:** running sandbox executions now terminate on authoritative cancellation and reconcile worker leases safely. Network-enabled execution remains fail-closed pending egress mediation.

## Repository checkpoint

Changes are committed to `main`. Use the GitHub Actions page to verify the current revision before deploying or applying database migrations.

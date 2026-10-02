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
- **Phase 6 — Autonomous ML Lifecycle (initial):** tenant-scoped training-run tracking, versioned model registry metadata, evaluation records, lifecycle rules, and a passing-evaluation plus human-note gate before model approval.

The research planner currently tracks plans and tasks; it does not autonomously run external tools or collect data. The ML lifecycle currently tracks training-run metadata, model records and evaluation results; it does not execute training code, load artifact URIs, deploy models or monitor live endpoints. These capabilities require later phases and explicit safety, evaluation and permission controls.

## Repository checkpoint

Changes are committed to `main`. Use the GitHub Actions page to verify the current revision before deploying or applying database migrations.

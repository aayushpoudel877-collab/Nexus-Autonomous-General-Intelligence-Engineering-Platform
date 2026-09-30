# NEXUS-Ω — Autonomous General Intelligence Engineering Platform

NEXUS-Ω is a long-horizon platform for autonomous AI engineering, research, experimentation, deployment, learning, and multimodal intelligence.

## Vision

NEXUS-Ω combines an autonomous AI engineering control plane with a production web platform and an integrated Learning Management System (LMS). The platform is designed to evolve through measurable research and engineering loops while keeping humans in control of consequential actions.

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

## Status

Phase 2 — LMS foundation implemented. Includes course authoring, modules, lessons, enrollment, progress tracking, assessments, grading, learner dashboard and PostgreSQL migrations.\n\nPhase 1 identity foundation remains the security and tenancy layer.

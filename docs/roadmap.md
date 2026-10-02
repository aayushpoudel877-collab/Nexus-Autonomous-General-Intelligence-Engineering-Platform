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
Text, image, audio, video and structured-data pipelines with unified evaluation.

## Phase 8 — Continuous Improvement
Failure analysis, benchmark generation, experiment prioritization and bounded improvement loops.

## Phase 9 — Production Hardening
Security, reliability, scale, disaster recovery, governance and cost controls.

## Phase 10 — Ecosystem
SDKs, plugins, integrations and developer APIs.

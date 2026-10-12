# NEXUS-Ω — Autonomous General Intelligence Engineering Platform

NEXUS-Ω is a research-driven monorepo for building governed autonomous AI systems, AI-assisted software engineering, learning experiences, and intelligent orchestration. The long-term product combines multimodal intelligence, research and engineering workflows, an LMS and AI tutor, persistent data services, identity/tenancy, a web control plane, and deployment/observability infrastructure.

## Architecture at a glance

- **`apps/web`** — Next.js web application, operator workspace, and LMS.
- **`services/api`** — FastAPI endpoints, authorization, and application contracts.
- **`services/orchestrator`** — durable workflow scheduling, leases, replay, and recovery planning.
- **`services/ai-core`** — model/provider abstraction and agent-runtime foundations.
- **`services/learning`** — learning-domain services.
- **`services/rag`** — provider-independent retrieval, evidence packaging, grounding checks, evaluation, and persistent corpus helpers.
- **`packages/shared`** — shared domain contracts.
- **`migrations`** — PostgreSQL/Alembic schema evolution.
- **`infra`** — local and deployment infrastructure.
- **`docs`** — architecture, security boundaries, phase plans, and evaluation protocols.

## Engineering principles

- Tenant and authorization checks fail closed.
- Autonomous actions remain within explicit policy and human-approval boundaries.
- State transitions are observable and durable.
- Experiments and artifacts should be reproducible and versioned.
- External providers and runtimes are replaceable; untrusted content is data, never instructions.
- A phase is complete only when acceptance criteria, tests, documentation, and security review are recorded.

## Implemented foundations and boundaries

- **Identity and core platform:** authentication, refresh sessions, organization membership/roles, and audit events. Ambiguous multi-organization membership fails closed pending explicit organization selection.
- **LMS and AI tutor:** course authoring, enrollment, progress, assessments/grading, and persisted tutor conversations with an explicitly disclosed local fallback. A hosted LLM adapter is not yet connected.
- **Research and ML lifecycle:** research plans/tasks, experiment and training-run metadata, model registry/evaluation records, and explicit approval gates. The research planner does not autonomously collect external data, and the ML lifecycle does not run arbitrary training code.
- **Multimodal and continuous improvement:** tenant-scoped asset manifests and baseline/candidate metric comparisons. Asset bytes are not decoded/inferred on, and caller-submitted benchmark metrics are not independently verified.
- **Platform hardening and ecosystem:** request correlation, trusted-host/security-header handling, readiness checks, API keys/scopes, plugin metadata, and a lightweight SDK. Plugin registration does not itself execute third-party code.
- **Governed execution:** approved installations/releases, artifact trust and content-addressed staging, optional isolated OCI runtime, cooperative cancellation, controlled egress mediation, and secret-grant checks. Runtime launch is disabled by default; secret-enabled execution remains fail-closed without a configured external provider.
- **Durable workflows:** tenant-scoped DAGs, persisted runs and node state, worker leases/retries, ordered event history, deterministic replay/drift analysis, and read-only governed recovery recommendations.
- **RAG retrieval core:** normalized text chunking, tenant-scoped lexical retrieval with tunable BM25, dense-score fusion, document filters, source-diversity limits, evidence packaging, provider-neutral embedding contracts, bounded batching, model-version validation, tenant-scoped LRU caching, weighted reciprocal-rank fusion, and offline precision/recall/MRR/NDCG metrics.
- **RAG persistent corpus (feature branch foundation):** organization-scoped document/chunk records, exact-content SHA-256 deduplication, bounded metadata and text ingestion, and monotonic lifecycle transitions. Phase 28 adds authenticated, organization-scoped corpus routes and bounded lexical query responses. Hosted embedding providers, durable vector indexing, API integration of semantic retrieval, binary document parsing, grounded LLM generation, semantic entailment evaluation and deletion propagation to external indexes are not yet implemented. The in-memory vector store is for tests/local demos only.

These are scoped foundations, not a claim that the complete long-term platform is production-ready. Full distributed rate limiting, tracing, secret rotation, disaster recovery, binary multimodal processing, verified benchmark execution, vector indexing, semantic entailment evaluation, and multilingual/low-resource retrieval remain future work.

## Development

Python requirements and optional development dependencies are defined in `pyproject.toml`. The web application has its own package configuration under `apps/web`.

Typical checks from the repository root:

```bash
pip install -e '.[dev]'
ruff check .
pytest
cd apps/web
npm install
npm run build
```

Run database migrations using the repository's Alembic configuration and a correctly configured database URL. Review migration upgrade/downgrade behavior and CI results for the exact commit before deploying.

## Roadmap and project status

- `docs/architecture.md` describes system boundaries and security assumptions.
- `docs/roadmap.md` describes the platform's long-horizon delivery plan.
- `docs/rag/roadmap.md` and `docs/rag/evaluation-protocol.md` describe RAG phases and release gates.

The default branch and feature branches can contain different capabilities. Verify the branch, pull request state, and GitHub Actions checks for the exact revision you intend to use. Do not treat a feature branch as merged or deployment-ready solely because its tests pass.

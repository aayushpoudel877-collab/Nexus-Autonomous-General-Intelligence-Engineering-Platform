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
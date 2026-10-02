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

# Phase 35 — Observability and Governance

## Scope and implementation status

This phase adds deterministic contracts that application services can safely persist and dispatch. It does not silently enable a telemetry vendor, external vector index, automatic data deletion, or model approval workflow.

## Privacy-safe audit events

`services.rag.governance.build_audit_event` accepts a strict allowlist of event types and outcome labels. It records opaque organization/actor/resource/trace identifiers, UTC time, bounded duration and evidence count. It has no fields for query text, prompt, retrieved text, credentials, or source URI. Callers must avoid embedding personal or confidential data in opaque identifiers.

## Source lineage

The lineage contract captures tenant, document/chunk identifiers, a SHA-256 content digest, source version, parser version and indexed timestamp. It deliberately excludes raw content and source URLs. A digest is provenance metadata, not proof that a source is trustworthy.

## Deletion propagation

A deletion request has a deterministic idempotency key derived from tenant, document and content digest. The request starts in `pending`; an acknowledgement helper allows a caller to create an acknowledged snapshot after its external index confirms deletion. Production integration must persist this in a transactional outbox, retry transient failures, monitor dead letters, and ensure tenant scope is part of every external index operation. This module does not claim external deletion has occurred.

## Retention

`RetentionPolicy` defines bounded event, trace and lineage windows. `retention_expired` is a pure decision helper; a scheduler, legal hold policy and storage-specific deletion adapter are still required to execute retention. Defaults are not legal advice and must be reviewed for the deployment's jurisdiction and contracts.

## Model cards

The model-card contract requires intended use, limitations, evaluation dataset/date, owner, version and a controlled approval status. Validation checks completeness and date syntax only. Approval must remain a human governance action and should reference reviewed, representative evaluation data. The existing RAG fixtures are synthetic contract tests and are not production evidence.

## Acceptance checklist

- [x] Strict privacy-safe event schema with bounded fields.
- [x] Versioned source lineage without raw content.
- [x] Idempotent external-index deletion request contract and acknowledgement transition.
- [x] Bounded retention policy and expiry decision.
- [x] Model-card completeness validation with explicit status.
- [x] Unit tests for invalid values, privacy boundaries and idempotency.
- [ ] Persisted transactional outbox and worker against a configured external index.
- [ ] Storage-specific retention scheduler, legal holds and verified erasure.
- [ ] Production tracing backend, dashboards, alerting and access-controlled trace UI.
- [ ] Human-reviewed multilingual benchmark and formal model-card approval.

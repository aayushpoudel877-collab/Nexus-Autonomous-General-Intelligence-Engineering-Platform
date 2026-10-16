# RAG Phase 39 — Graph-Assisted Retrieval Hardening

## Implemented safeguards

Graph expansion consumes explicit, caller-supplied entity/chunk associations. It does not extract entities automatically, issue arbitrary graph queries, or replace the seed retrieval strategy.

This increment adds:
- A maximum seed candidate count, entity count, total entity-to-chunk associations, and existing edge/fanout/hop limits.
- Validation that each entity's chunk associations are a sequence rather than an accidental string or bytes object.
- Rejection of negative seed scores because multiplicative hop decay assumes non-negative ranking scores.
- Regression tests for each new boundary and existing tenant-isolation behavior.

## Limits

The graph remains in-memory and receives associations from its caller. It has no durable graph database, automatic entity extraction, reviewed production graph corpus, or measured retrieval ablation. Entity labels and relation text are untrusted data and must not be treated as instructions by any downstream agent.

## Remaining acceptance

- Add human-reviewed entity/relation and query relevance sets.
- Measure graph-assisted retrieval against lexical-only and hybrid baselines, including per-language and tenant-isolation checks.
- Evaluate noisy, duplicate, cyclic, and adversarial edges under realistic graph density.
- Introduce durable graph persistence only with ownership constraints, deletion propagation, and bounded query plans.

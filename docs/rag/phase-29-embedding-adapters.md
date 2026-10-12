# Phase 29 — Embedding adapter and vector-store contracts

## Scope

This phase introduces the provider-independent contracts required to add semantic retrieval without binding the RAG core to a specific model vendor.

Delivered in this branch:

- Immutable model identity includes provider, model name, version and vector dimensions.
- Embedding vectors validate dimension count and reject NaN/infinite values.
- Async embedding orchestration batches inputs with configurable, bounded batch sizes, validates input length and preserves result order.
- A provider protocol separates model SDKs and credentials from the retrieval core.
- A vector-store protocol defines upsert, tenant-scoped nearest-neighbor search and tenant-scoped document deletion.
- A deterministic in-memory cosine-similarity implementation supports local tests and demos.
- Contract tests cover ordering, bounds, vector validation, tenant isolation, idempotent upsert, ranking and deletion.

## Provider implementation contract

A concrete adapter must expose a stable `EmbeddingModel` value and implement `embed(texts)`. It must return exactly one vector for each input, in input order. The orchestration layer checks dimensions and finite values before returning results. Provider-specific retry policy, timeout handling, credentials, rate-limit headers and billing controls belong in the adapter layer; this phase does not claim to implement those provider-specific concerns.

## Vector-store safety contract

Every record carries a tenant, document and chunk identifier. Searches require an explicit tenant and must filter inside the storage query. Deletion requires both tenant and document identifiers. Implementations must never compare vectors from different model versions or dimensions. A durable backend must also make index writes idempotent and propagate document deletion to all index replicas.

The in-memory backend intentionally supports one embedding model version per instance and is not suitable for production persistence, concurrency or large corpora.

## Example

```python
model = EmbeddingModel(
    provider="local",
    model="example-encoder",
    version="2026-01",
    dimensions=3,
)
vector = EmbeddingVector(model, (0.1, 0.2, 0.3))
record = VectorRecord(
    tenant_id="org-123",
    document_id="doc-456",
    chunk_id="chunk-001",
    text="Example source text",
    embedding=vector,
)
```

## Explicitly not implemented

- No hosted embedding provider is configured or called.
- No API endpoint writes embeddings or uses vector search yet.
- No PostgreSQL/pgvector migration or durable vector index is included.
- No distributed rate limiter, provider retries, timeout/budget policy, or credential management is included.
- No model migration/backfill job or deletion propagation worker is included.
- The existing API query path remains lexical until a durable index and rollout controls are integrated.

## Acceptance criteria for this contract layer

- Invalid model metadata and malformed vectors fail closed.
- Batches stay within configured limits and preserve input order.
- Cross-tenant records are never returned by the reference search implementation.
- Incompatible model versions cannot be compared.
- Deletion only affects the specified tenant and document.
- Tests and CI validate the contract independently of external provider credentials.

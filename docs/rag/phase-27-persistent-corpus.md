# Phase 27 — Persistent RAG Corpus

## Schema and invariants
- `rag_documents` stores organization ownership, title/source metadata, a SHA-256 fingerprint of the exact original UTF-8 text, character count, lifecycle status, and timestamps.
- `rag_chunks` stores organization and document ownership, ordinal, normalized extracted text, source offsets into the normalized text, a whitespace-based token estimate, and timestamp.
- A unique organization/content hash constraint makes exact-content ingestion idempotent within an organization while allowing the same content in different organizations.
- Database checks constrain status values, non-negative ordinals, and positive source spans. A composite foreign key enforces that each chunk and its parent document have the same organization; physical document deletion cascades to chunks.
- Ingestion is bounded to 2,000,000 source characters, chunk sizes of 100–12,000 characters, and JSON metadata of at most 16 KiB. These limits protect the persistence boundary; API-level request limits are still required.

## Transaction contract
`ingest_document` does not commit. The API/service caller owns transaction boundaries and must commit or roll back explicitly. The fingerprint is computed from original text, while chunks are produced from normalized text and offsets refer to that normalized representation. Existing active content returns the prior record without duplicating chunks; matching archived/deleted content fails closed.

Concurrent duplicate ingestion is protected by a savepoint. If the unique organization/content-hash constraint wins a race, the helper reloads and returns the active organization-scoped record without invalidating the caller's outer transaction. This recovery assumes PostgreSQL READ COMMITTED isolation; unrelated integrity errors are re-raised for the caller to handle.

## Lifecycle contract
- `active -> archived`, `active -> deleted`, and `archived -> deleted` are permitted.
- Repeating the current status is idempotent.
- Archived/deleted documents cannot be reactivated through the status helper. A future restore workflow must be explicit and audited.
- `deleted` is a soft-delete status. Physical deletion and its cascade behavior are separate database operations.

## Authorization contract
The API must derive `organization_id` from authenticated membership context, never trust a tenant ID submitted by a client. Repository reads and state updates include organization predicates. This database layer is defense in depth, not a replacement for route authorization. Do not dereference `source_uri` from the API process.

## Limitations and release gates
This phase stores document/chunk records only. It does not parse uploaded binary files, embed content, index vectors, call an LLM, or prove semantic support. Citation checks validate reference structure, not entailment. Before exposing this through an API, add route authorization tests, transaction/integrity-conflict tests against PostgreSQL, migration upgrade/downgrade checks, and audit coverage for lifecycle changes.

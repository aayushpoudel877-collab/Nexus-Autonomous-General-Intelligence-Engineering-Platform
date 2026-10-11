# Phase 27 — Persistent RAG Corpus

## Schema
- \`rag_documents\`: organization ownership, title/source metadata, SHA-256 content fingerprint, character count, lifecycle status, and timestamps.
- \`rag_chunks\`: organization and document ownership, ordinal, extracted text, source offsets, token estimate, and timestamp.
- A unique organization/content hash constraint makes identical content idempotent within an organization while allowing the same content to exist in different organizations.
- Foreign keys cascade document deletion to chunks. Status transitions are limited to active, archived, and deleted.

## Transaction contract
\`ingest_document\` does not commit. The API/service caller owns transaction boundaries and must commit or roll back explicitly. Ingestion hashes the original UTF-8 source content, chunks normalized text, and stores offsets into that normalized text. Existing active content returns the prior record without duplicating chunks; matching archived/deleted content fails closed.

## Authorization contract
The API must derive \`organization_id\` from the authenticated membership context, never trust a tenant ID submitted by the client. Repository reads and state updates include organization predicates. The database layer is defense in depth, not a replacement for route authorization.

## Limitations
This phase stores document/chunk records only. It does not parse uploaded binary files, embed content, index vectors, call an LLM, or prove semantic support. Concurrent duplicate ingestion can still race; the unique constraint is authoritative and the caller should handle integrity conflicts with a transaction retry.

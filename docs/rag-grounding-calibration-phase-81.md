# Phase 81 — Guided RAG Studio

## Goal

Make the existing RAG ingestion and retrieval capabilities understandable and approachable to everyday workspace users, without implying that capabilities not connected to the API are available.

## User experience

- Add a dedicated `/rag-studio` workspace with a guided three-step explanation: add sources, build the knowledge library, and ask with evidence.
- Support bounded document upload for TXT, Markdown, HTML, PDF, and DOCX through the existing multipart upload API.
- Support pasting text through the existing document-create API.
- Show active source counts, stored character totals, source metadata, duplicate-ingestion feedback, and organization-scope messaging.
- Query the active knowledge base and show ranked evidence passages, source links, character offsets, and expandable text.
- Collect useful / not-useful feedback through the existing metadata-conscious feedback endpoint.
- Allow users with the required role to remove a document from active retrieval.
- Link the new workspace from the homepage and the advanced operator workbench.
- Provide responsive layouts and clear loading, empty, success, permission, and error states.

## Honest capability boundaries

The current query API performs lexical retrieval with optional character n-gram matching. The Studio labels the mode accordingly and displays source passages rather than fabricating an AI-generated answer. It explicitly explains that ranking scores are not factual confidence and that a hosted answer-generation provider is not currently connected.

Ingestion is a synchronous API request that extracts text, chunks it, and persists it. The UI does not display fabricated background-job progress. The existing API continues to enforce authentication, organization scope, role permissions, upload limits, and supported file formats.

## Validation

The pull request must pass the repository's complete CI workflow, including the Next.js production build, Python lint/tests, PostgreSQL migration/idempotency checks, and container builds.

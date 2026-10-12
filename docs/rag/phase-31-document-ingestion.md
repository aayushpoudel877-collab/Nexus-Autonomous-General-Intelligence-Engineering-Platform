# Phase 31 — Bounded document ingestion

## Scope

Phase 31 adds a parser boundary between uploaded bytes and the existing persistent RAG corpus. The new authenticated endpoint is:

`POST /api/v1/rag/documents/upload` (multipart form data)

Form fields: `file` (required), `title` (optional), `source_uri` (optional), `max_chars` (100–12,000, default 1,200), and `overlap` (default 160; must be smaller than `max_chars`).

Supported formats:

| Extension | Parser | Notes |
|---|---|---|
| .txt, .md | UTF-8 text | UTF-8 BOM is accepted; invalid UTF-8 is rejected |
| .html, .htm | HTML visible-text extractor | Script, style, SVG, template, noscript, and head content are ignored |
| .pdf | pypdf | Encrypted PDFs are rejected; scanned/image-only pages need OCR, which is not included |
| .docx | python-docx | Paragraph and table text are extracted; legacy .doc is not supported |

## Guardrails

- Upload bytes are capped at 10 MiB before parsing; extracted text is capped at 2,000,000 characters.
- The filename extension and declared MIME type must agree (or the MIME type must be generic/absent). PDF and DOCX content signatures/containers are checked.
- Unsupported types, malformed files, empty extraction, invalid text encoding, and limit violations return a validation error rather than being silently ingested.
- The server stores parser name, normalized media type, sanitized filename, byte count, and extracted character count as ingestion provenance in document metadata and audit details.
- The endpoint uses the existing owner/admin/instructor role gate, organization membership, corpus idempotency, chunking, and audit pipeline.
- Extracted content remains untrusted data. Parsing does not execute scripts or macros. Malware scanning, OCR, asynchronous quarantine/dead-letter processing, archive-wide scanning, and antivirus integration are explicitly not claimed as implemented.

## Dependency setup

Install the document extra for PDF and DOCX support:

`pip install -e '.[documents,dev]'`

The base package keeps parser SDKs optional; the multipart API dependency is installed with the normal project dependencies. CI installs the document libraries via the dev extra so parser tests can run.

## Acceptance checklist

- [x] Bounded upload extraction and strict supported-format allowlist.
- [x] Text, Markdown, and HTML visible-text extraction.
- [x] PDF and DOCX adapters with explicit malformed/unsupported errors.
- [x] Authenticated, role-gated multipart endpoint and tenant-scoped persistence.
- [x] Parser provenance and upload audit details.
- [x] Unit tests for MIME mismatch, malformed input, empty extraction, filename sanitization, and size limits.
- [ ] Dedicated PostgreSQL integration tests for the multipart endpoint.
- [ ] Malware scanning/quarantine and durable dead-letter retries.
- [ ] OCR for scanned documents and extraction quality evaluation.

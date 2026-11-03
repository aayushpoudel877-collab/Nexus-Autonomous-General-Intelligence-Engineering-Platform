# Phase 79 — Strict GitHub API response decoding

## Goal

Harden the trusted-review ingestion boundary so authenticated GitHub API responses are not interpreted ambiguously before governance checks run.

## Changes

- Add a shared strict UTF-8 JSON decoder for GitHub API response bytes.
- Reject duplicate keys at every nesting level rather than silently accepting the last value.
- Reject non-standard numeric constants such as NaN and positive/negative Infinity.
- Reject malformed JSON, invalid UTF-8, and excessive parser recursion with a bounded validation error.
- Integrate strict decoding into the bounded GitHub response reader.
- Validate the pull-request endpoint's top-level object shape immediately, before requesting review pages.
- Add focused decoder and transport-boundary regression tests.

## Security boundaries

TLS and the authenticated GitHub API request remain the source of live API transport authenticity. Strict JSON decoding prevents ambiguous or non-standard payload interpretation; it does not independently authenticate GitHub, replace TLS, or establish reviewer identity. Existing response byte, page, and review-count limits remain in force.

## Validation

The full CI workflow remains the acceptance gate: Python lint/tests, web production build, PostgreSQL migration/idempotency checks, and container builds.

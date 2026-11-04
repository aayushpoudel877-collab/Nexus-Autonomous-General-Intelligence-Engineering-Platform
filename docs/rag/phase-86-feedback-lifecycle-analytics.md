# RAG Phase 86 — Feedback lifecycle analytics

Phase 86 adds a daily UTC trend over the existing RAG feedback audit events. It distinguishes submissions from status transitions into triaged, resolved, and ignored states. The query is bounded to 7–90 days, derives organization scope from authenticated membership, and aggregates in the database. Missing dates are zero-filled.

The operator workbench displays lifecycle totals and daily activity alongside the feedback trend and backlog aging views. The metric counts audit actions rather than unique feedback records: one item may contribute a submission and one or more subsequent transitions.

Only aggregate counts are returned. Audit actors, resource IDs, query digests, notes, and evidence IDs remain excluded. No schema migration or new audit event writes are introduced.

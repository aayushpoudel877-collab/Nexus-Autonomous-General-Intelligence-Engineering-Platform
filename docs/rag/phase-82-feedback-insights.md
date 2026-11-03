# RAG Phase 82 — Feedback insights

This phase adds an organization-scoped aggregate view over existing `RAGFeedback` records and surfaces it in the operator workbench.

The aggregate endpoint reports counts by rating and workflow status, total feedback, and the helpful percentage. It returns no query text, query digest, note, actor ID, or evidence ID. The existing role policy (owner/admin/instructor) is applied, and the query is constrained by the authenticated organization ID.

The operator UI uses the aggregate response to explain user engagement and feedback triage workload. A helpful rating is not a correctness label; it is only a user-reported usefulness signal. A missing sample returns a null percentage.

No schema migration or provider integration is introduced. Existing retrieval and reindex behavior remains unchanged.

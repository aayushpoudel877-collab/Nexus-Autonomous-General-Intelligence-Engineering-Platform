# RAG Phase 84 — Feedback period comparison

Phase 84 adds a tenant-scoped endpoint that compares two adjacent, complete UTC periods of equal length (7–90 days). Database-side aggregation returns helpful/unhelpful/total counts and changes without returning individual feedback records. The response reports absolute count deltas, relative count deltas where a non-zero prior baseline exists, and helpful-rate percentage-point movement where both periods contain feedback.

The RAG Operator Workbench presents the comparison alongside the daily activity chart. It uses the existing 7/30/90-day selector and clearly distinguishes the completed-day comparison windows from the daily chart's displayed range.

Feedback remains a user-perceived usefulness signal, not a factuality or semantic-correctness label. Relative change is omitted when the previous count is zero, and helpful-rate movement is omitted when either period has no feedback. No schema migration is introduced.

# RAG Phase 83 — Feedback activity trends

Phase 83 adds a daily UTC time series over the existing feedback records. The endpoint accepts a bounded 7–90 day window, aggregates helpful and unhelpful ratings in the database, and fills missing days with zeros. The active organization is derived from authenticated membership and applied to the query.

The operator workbench adds a time-window selector and a daily activity visualization. The visualization is descriptive only: user feedback is not a ground-truth relevance or factuality label. No raw query, digest, note, actor, or evidence identifiers are returned by the trend endpoint.

No schema migration or new persistence is introduced. The existing lexical retrieval behavior remains unchanged.

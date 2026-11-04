# RAG Phase 90 — Bulk triage preview

Phase 90 adds a read-only preview endpoint for a selected bulk feedback transition. It reports eligible, unchanged, and blocked counts without returning feedback IDs or individual fields. The operator workbench shows this preview and only enables Apply when all selected records can make the requested transition.

A preview is not a lock or reservation. The apply endpoint continues to acquire row locks and revalidate the entire batch before mutation, so a concurrent status change between preview and apply cannot cause a partial update. No schema migration or new audit writes are introduced by preview.

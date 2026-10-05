[object Object]

## Phase 19 secret-grant governance

Secret values are never exposed through governance APIs. A secret grant response exposes only opaque grant identity, installation/integration linkage, review state and approval metadata.

Available controls:

- request a grant for an approved installation and active integration with an external secret reference;
- owner/admin approval with a required review note;
- revoke a grant;
- require `secret.read` in the plugin installation approval and execution capabilities.

The execution worker rechecks grant state immediately before sandbox startup, so revocation and integration disablement take effect without modifying historical policy snapshots.

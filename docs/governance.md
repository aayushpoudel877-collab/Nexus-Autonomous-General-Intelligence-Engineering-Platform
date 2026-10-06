[object Object]

## Phase 19 secret-grant governance

Secret values are never exposed through governance APIs. A secret grant response exposes only opaque grant identity, installation/integration linkage, review state and approval metadata.

Available controls:

- request a grant for an approved installation and active integration with an external secret reference;
- owner/admin approval with a required review note;
- revoke a grant;
- require `secret.read` in the plugin installation approval and execution capabilities.

The execution worker rechecks grant state immediately before sandbox startup, so revocation and integration disablement take effect without modifying historical policy snapshots.


## Phase 20 secret-lease governance

Secret grants now require a bounded expiration at approval time. Approval must include an explicit expiration between one minute and seven days from the review time.

The governance lifecycle now treats revoked grant IDs as permanently retired. A later request for the same installation/integration receives a new grant identity, so an older execution snapshot cannot regain access after revocation.

Legacy non-revoked grants are expired during migration 0020 and must be explicitly approved again.

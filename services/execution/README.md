[object Object]

## Phase 19 mediated secrets

Secret-enabled executions require the `secret.read` capability and one or more approved `SecretGrant` IDs.

The grant workflow is:

1. an active integration stores an external `secret://...` reference;
2. a tenant plugin installation is approved with `secret.read`;
3. a secret-grant request binds that installation to the integration;
4. an owner/admin explicitly approves the grant; and
5. an execution freezes only the opaque grant IDs in policy version 4.

At runtime the worker revalidates the grants against the current database state. Revoked grants and disabled integrations are rejected before sandbox launch.

The worker starts a short-lived secret-broker subprocess for secret-enabled executions. The broker receives a per-execution token and grant mapping. The sandbox receives only:

- `NEXUS_SECRET_SOCKET=/nexus/secrets.sock`
- `NEXUS_SECRET_TOKEN_FILE=/nexus/secrets.token`

The secret broker protocol is JSON Lines:

`{"token":"...","grant_id":"..." }`

A successful response contains a base64-encoded secret value only for the requested approved grant. The broker does not cache values and never records secret payloads in audit events, execution results, failure reasons or files.

The actual secret manager is supplied by the deployment through `NEXUS_SECRET_PROVIDER_COMMAND`. The command is invoked without a shell and receives `{"secret_ref":"secret://..." }` on stdin. Its stdout must return `{"ok":true,"secret":"..." }`. The default is unset, so secret-enabled execution fails closed.

### Secret configuration

- `NEXUS_SECRET_PROVIDER_COMMAND` — external secret-provider command; unset by default.


## Phase 20 secret leases

Secret-enabled executions use policy snapshot version 5. Approved `secret.read` grants have a bounded one-minute-to-seven-day lease. The worker revalidates that lease immediately before sandbox launch, and revoked grant IDs are permanently retired so a historical execution cannot regain access after a later approval.

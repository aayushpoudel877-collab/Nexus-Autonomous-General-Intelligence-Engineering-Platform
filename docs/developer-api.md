[object Object]

## Phase 19 secret grants

The governance API introduces:

- `GET /api/v1/governance/secret-grants`
- `POST /api/v1/governance/secret-grants`
- `POST /api/v1/governance/secret-grants/{grant_id}/approve`

A grant request binds an approved plugin installation to one active integration that contains an external `secret://...` reference. The API never returns that underlying reference in the grant response.

Execution requests can include `secret_grant_ids` together with the `secret.read` capability. The API verifies that every grant is approved for the same installation, the integration is active, and the grant belongs to the tenant.

At runtime, secrets are delivered through a per-execution Unix-socket broker subprocess. They are not injected into plugin environment variables and are excluded from result JSON and audit detail.

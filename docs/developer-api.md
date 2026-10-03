# NEXUS-Ω Developer API

Phase 10 adds a tenant-scoped developer surface without granting direct database access or arbitrary code execution.

## Authentication

Owner and admin users can create developer API keys from:

- `POST /api/v1/developer/api-keys`

Keys use the `nxk_` prefix and are stored only as SHA-256 digests. The plaintext secret is returned once in the create response and is never returned by the list endpoint.

Send a key with:

```http
X-Nexus-API-Key: nxk_<prefix>_<secret>
```

Keys can have these scopes:

- `developer:read`
- `developer:write`
- `plugin:read`
- `plugin:write`

An expired or revoked key is rejected. API-key activity records the latest request time, while administrative creation and revocation are written to the organization audit stream.

## Plugin registry

The plugin registry is metadata-only in this phase. It lets an organization register a plugin manifest and lifecycle state without downloading or executing plugin code.

Available endpoints:

- `GET /api/v1/developer/whoami`
- `GET /api/v1/developer/plugins`
- `POST /api/v1/developer/plugins`
- `PATCH /api/v1/developer/plugins/{plugin_id}`

Plugin slugs are unique within an organization. All reads and writes are tenant-scoped by the API key's organization.

## Python SDK

The repository includes a dependency-free client under `packages/sdk`.

```python
from packages.sdk import NexusClient

client = NexusClient(
    "http://localhost:8000/api/v1",
    "nxk_<prefix>_<secret>",
)

print(client.whoami())
print(client.list_plugins())

client.create_plugin(
    slug="my-research-plugin",
    name="My Research Plugin",
    version="0.1.0",
    description="Research workflow integration metadata",
    manifest={"capabilities": ["research.plan.read"]},
)
```

The SDK is intentionally small so it can remain a stable transport boundary while richer generated clients and additional language SDKs are added later.

## Security boundary

This phase does not:

- execute plugin code,
- download plugin packages from arbitrary URLs,
- issue unrestricted root credentials,
- provide distributed rate limiting,
- persist plaintext API-key secrets,
- or dispatch outbound webhook events.

Those capabilities require separate isolation, policy, signing, rotation, and delivery controls.

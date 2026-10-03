# NEXUS-Ω Ecosystem Governance

Phase 11 adds a control plane around integrations and plugin supply chains.

## Integration connections

An integration connection stores:

- provider and connection name
- allowed integration scopes
- non-secret configuration metadata
- a `secret_ref` pointing to an external secret-management system
- active/disabled lifecycle state

The API rejects common secret-like configuration fields such as passwords, tokens, API keys and private keys. Secret values must not be placed in the NEXUS database.

Phase 11 does not make outbound calls for an integration. Connections are records and policy inputs for a later isolated delivery worker.

## Plugin releases

A plugin registration may publish release records containing:

- version
- artifact URI
- package SHA-256
- manifest SHA-256
- signer
- signature
- verification state

New releases start in `pending`. An owner or admin must explicitly verify or reject a release before it can be requested for installation.

The platform records digest and signature metadata but does not download, unpack or execute the artifact.

## Plugin installation approval

An installation request is tenant-scoped and must reference a verified release from the same organization.

Requested capabilities are carried into the installation request. An owner or admin can approve only a subset of the requested scopes, or revoke the request. This provides a human approval gate before a future plugin execution runtime can receive capabilities.

## Security boundary

Phase 11 intentionally does not provide:

- arbitrary plugin execution
- package downloads
- automatic signature trust
- secret-value storage
- outbound network dispatch
- webhook delivery
- unrestricted integration credentials

A future execution plane should add sandboxing, signed trust roots, package provenance, secret-manager integration, egress policy, resource limits and detailed execution audit trails before activating external code or network actions.


### Release manifest freezing

Each new release must supply a manifest SHA-256 that matches the canonical hash of the plugin manifest at release creation time. The canonical manifest is copied into the release as a snapshot. Installation and execution capability checks use that frozen snapshot rather than mutable current plugin metadata.

Legacy releases created before manifest snapshots were introduced remain non-executable until a new release is published with a frozen manifest.

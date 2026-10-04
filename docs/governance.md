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


## Execution worker controls

Phase 13 adds a separate worker process behind approved execution requests. A worker may claim only queued records, and its lease expires unless heartbeats continue. Completion requires the same worker identity that owns the active lease, so an abandoned or cancelled worker cannot overwrite a newer terminal state.

The worker records only bounded execution results and operational metadata in the audit stream. It remains fail-closed for external plugin packages: no artifact is downloaded, no signature is trusted automatically, no secret value is resolved, and no outbound network request is performed. Those controls remain prerequisites for the next plugin-runtime phase.


## Phase 14 artifact verification

Each organization can register Ed25519 trust roots identified by a stable `key_id`. Plugin release signatures are verified over the canonical ASCII SHA-256 digest of the supplied artifact bytes. The computed digest must exactly match the release's declared `package_sha256`, and the release signer must match the selected trust-root key ID.

A release cannot move to `verified` until cryptographic artifact verification succeeds and an owner/admin records a human review note. Installation approval and execution additionally require that the verification trust root remains active. Revoking a trust root therefore prevents subsequent activation of releases tied to that key without rewriting historical release records.

Phase 14 intentionally does not fetch `artifact_uri` values or unpack packages. The verification endpoint uses a bounded artifact payload so signature checks can be performed without introducing an arbitrary URL fetch or code-execution primitive.

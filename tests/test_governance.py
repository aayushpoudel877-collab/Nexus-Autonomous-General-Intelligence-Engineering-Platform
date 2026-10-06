import pytest
from pydantic import ValidationError

from services.api.app.db.base import Base
from services.api.app.schemas.ecosystem import PluginCreate
from services.api.app.schemas.integrations import (
    IntegrationCreate,
    PluginInstallationApproval,
    PluginReleaseCreate,
)


def test_phase_11_tables_are_registered():
    assert "integration_connections" in Base.metadata.tables
    assert "plugin_releases" in Base.metadata.tables
    assert "plugin_installations" in Base.metadata.tables
    assert "secret_grants" in Base.metadata.tables


def test_phase_11_routes_are_registered():
    from services.api.app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/governance/integrations" in paths
    assert "/api/v1/governance/integrations/{integration_id}" in paths
    assert "/api/v1/governance/plugins/{plugin_id}/releases" in paths
    assert "/api/v1/governance/plugin-releases/{release_id}/verify" in paths
    assert "/api/v1/governance/plugin-installations" in paths
    assert "/api/v1/governance/plugin-installations/{installation_id}/approve" in paths
    assert "/api/v1/governance/trust-roots" in paths
    assert "/api/v1/governance/trust-roots/{trust_root_id}/revoke" in paths
    assert "/api/v1/governance/plugin-releases/{release_id}/verify-artifact" in paths
    assert "/api/v1/governance/secret-grants" in paths
    assert "/api/v1/governance/secret-grants/{grant_id}/approve" in paths


def test_plugin_manifest_size_is_bounded():
    with pytest.raises(ValidationError):
        PluginCreate(
            slug="oversized",
            name="Oversized",
            version="1.0.0",
            manifest={"payload": "x" * 66_000},
        )


def test_integration_rejects_secret_values_in_config():
    with pytest.raises(ValidationError):
        IntegrationCreate(
            provider="github",
            name="unsafe",
            config={"access_token": "plaintext"},
        )


def test_plugin_release_requires_sha256_digests():
    with pytest.raises(ValidationError):
        PluginReleaseCreate(
            version="1.0.0",
            artifact_uri="registry://example/plugin-1.0.0.tar.gz",
            package_sha256="not-a-digest",
            manifest_sha256="a" * 64,
            signature="signed-manifest-placeholder",
            signer="release-bot",
        )


def test_installation_approval_schema_is_explicit():
    payload = PluginInstallationApproval(
        status="approved",
        approved_scopes=["plugin.read"],
        note="Reviewed by platform administrators.",
    )
    assert payload.status == "approved"
    assert payload.approved_scopes == ["plugin.read"]



def test_integration_requires_external_secret_reference():
    with pytest.raises(ValidationError):
        IntegrationCreate(
            provider="github",
            name="bad-secret-ref",
            secret_ref="plaintext-secret-value",
        )

    valid = IntegrationCreate(
        provider="github",
        name="valid-secret-ref",
        secret_ref="secret://vault/nexus/github/token",
    )
    assert valid.secret_ref.startswith("secret://")



def test_plugin_installation_scopes_must_be_declared_by_manifest():
    from services.api.app.routes.execution import _manifest_capabilities

    capabilities = _manifest_capabilities(
        {
            "capabilities": ["research.read", "dataset.read"],
            "entrypoints": ["research.run"],
        }
    )
    assert "research.read" in capabilities
    assert "network.admin" not in capabilities



def test_developer_api_key_schema_accepts_all_supported_scopes():
    from services.api.app.schemas.ecosystem import DeveloperApiKeyCreate

    payload = DeveloperApiKeyCreate(
        name="all-scopes",
        scopes=[
            "developer:read",
            "developer:write",
            "plugin:read",
            "plugin:write",
            "plugin:release",
            "plugin:install",
            "plugin:execute",
            "integration:read",
            "integration:write",
        ],
    )
    assert len(payload.scopes) == 9


def test_review_payloads_normalize_notes():
    from services.api.app.schemas.integrations import (
        PluginInstallationApproval,
        PluginReleaseVerification,
    )

    release = PluginReleaseVerification(status="verified", note="  reviewed  ")
    installation = PluginInstallationApproval(
        status="approved",
        approved_scopes=["dataset.read"],
        note="  approved  ",
    )
    assert release.note == "reviewed"
    assert installation.note == "approved"



def test_plugin_manifest_hash_is_canonical():
    from services.api.app.services.ecosystem import canonical_manifest_sha256

    manifest = {
        "entrypoints": ["plugin.run"],
        "capabilities": ["dataset.read", "model.read"],
    }
    first = canonical_manifest_sha256(manifest)
    reordered = canonical_manifest_sha256(
        {
            "capabilities": ["dataset.read", "model.read"],
            "entrypoints": ["plugin.run"],
        }
    )
    assert first == reordered
    assert len(first) == 64


def test_execution_scope_validation_uses_release_manifest_snapshot():
    from services.api.app.routes.execution import _manifest_capabilities, _manifest_entrypoints

    snapshot = {
        "capabilities": ["dataset.read"],
        "entrypoints": ["plugin.run"],
    }
    assert _manifest_capabilities(snapshot) == {"dataset.read"}
    assert _manifest_entrypoints(snapshot) == {"plugin.run"}



def test_trust_root_schema_requires_ed25519():
    from services.api.app.schemas.artifacts import PluginTrustRootCreate

    payload = PluginTrustRootCreate(
        key_id="release-key-1",
        name="Primary release key",
        public_key="A" * 44,
    )
    assert payload.algorithm == "ed25519"


def test_artifact_verification_schema_bounds_payload():
    from services.api.app.schemas.artifacts import PluginArtifactVerification

    payload = PluginArtifactVerification(
        trust_root_id="00000000-0000-0000-0000-000000000000",
        artifact_base64="AAAA",
    )
    assert payload.artifact_base64 == "AAAA"


def test_secret_grant_schemas_are_opaque():
    from services.api.app.schemas.secrets import SecretGrantApproval, SecretGrantCreate

    request = SecretGrantCreate(
        installation_id="00000000-0000-0000-0000-000000000001",
        integration_id="00000000-0000-0000-0000-000000000002",
    )
    approval = SecretGrantApproval(status="approved", note="  reviewed  ")
    assert request.installation_id
    assert approval.note == "reviewed"
    assert not hasattr(request, "secret_ref")


def test_secret_grant_live_identity_is_unique_but_revoked_ids_can_be_reissued():
    from services.api.app.models.secrets import SecretGrant

    indexes = {
        index.name: index
        for index in SecretGrant.__table__.indexes
    }
    live_index = indexes["uq_secret_grant_org_installation_integration_live"]
    assert live_index.unique is True
    assert "status <> 'revoked'" in str(live_index.dialect_options["postgresql"]["where"])


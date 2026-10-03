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


def test_phase_11_routes_are_registered():
    from services.api.app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/governance/integrations" in paths
    assert "/api/v1/governance/integrations/{integration_id}" in paths
    assert "/api/v1/governance/plugins/{plugin_id}/releases" in paths
    assert "/api/v1/governance/plugin-releases/{release_id}/verify" in paths
    assert "/api/v1/governance/plugin-installations" in paths
    assert "/api/v1/governance/plugin-installations/{installation_id}/approve" in paths


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

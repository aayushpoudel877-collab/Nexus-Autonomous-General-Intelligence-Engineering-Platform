import pytest

from services.execution.sandbox import (
    build_oci_command,
    validate_artifact_digest,
    validate_sandbox_image,
)


def test_sandbox_image_must_be_digest_pinned():
    with pytest.raises(ValueError):
        validate_sandbox_image("python:3.12")


def test_sandbox_command_is_non_networked_and_read_only():
    built = build_oci_command(
        image="registry.example/nexus-runtime@sha256:" + "a" * 64,
        artifact_path="/var/lib/nexus/artifacts/aa/bb/" + "b" * 64,
        entrypoint="plugin.run",
        max_memory_mb=512,
        cidfile="/var/lib/nexus/runtime/cid/test.cid",
    )

    command = built.command
    assert "--network=none" in command
    assert "--read-only" in command
    assert "--cap-drop=ALL" in command
    assert "--security-opt=no-new-privileges" in command
    assert any(item.startswith("--memory=512m") for item in command)
    assert built.image.endswith("@sha256:" + "a" * 64)


def test_sandbox_command_rejects_non_absolute_artifact_path():
    with pytest.raises(ValueError):
        build_oci_command(
            image="registry.example/nexus-runtime@sha256:" + "a" * 64,
            artifact_path="relative/artifact",
            entrypoint="plugin.run",
            max_memory_mb=512,
        )


def test_sandbox_command_rejects_embedded_newline_entrypoint():
    with pytest.raises(ValueError):
        build_oci_command(
            image="registry.example/nexus-runtime@sha256:" + "a" * 64,
            artifact_path="/artifact",
            entrypoint="plugin.run\nmalicious",
            max_memory_mb=512,
        )



def test_sandbox_rejects_null_bytes_in_entrypoint():
    with pytest.raises(ValueError):
        build_oci_command(
            image="registry.example/nexus-runtime@sha256:" + "a" * 64,
            artifact_path="/artifact",
            entrypoint="plugin\x00.run",
            max_memory_mb=512,
            cidfile="/runtime/cid/test",
        )


def test_sandbox_validates_artifact_digest():
    assert validate_artifact_digest("a" * 64) == "a" * 64

    with pytest.raises(ValueError):
        validate_artifact_digest("not-a-digest")


def test_sandbox_can_mount_mediated_egress_socket_and_token():
    built = build_oci_command(
        image="registry.example/nexus-runtime@sha256:" + "a" * 64,
        artifact_path="/var/lib/nexus/artifacts/aa/bb/" + "b" * 64,
        entrypoint="plugin.run",
        max_memory_mb=512,
        cidfile="/var/lib/nexus/runtime/cid/test.cid",
        egress_socket_path="/var/lib/nexus/runtime/egress/test.sock",
        egress_token_path="/var/lib/nexus/runtime/egress/test.token",
    )
    assert "--network=none" in built.command
    assert "type=bind,src=/var/lib/nexus/runtime/egress/test.sock,dst=/nexus/egress.sock,readonly" in built.command
    assert "type=bind,src=/var/lib/nexus/runtime/egress/test.token,dst=/nexus/egress.token,readonly" in built.command
    assert "--env=NEXUS_EGRESS_SOCKET=/nexus/egress.sock" in built.command
    assert "--env=NEXUS_EGRESS_TOKEN_FILE=/nexus/egress.token" in built.command


def test_sandbox_requires_egress_socket_and_token_together():
    with pytest.raises(ValueError):
        build_oci_command(
            image="registry.example/nexus-runtime@sha256:" + "a" * 64,
            artifact_path="/artifact",
            entrypoint="plugin.run",
            max_memory_mb=512,
            egress_socket_path="/tmp/egress.sock",
        )


def test_sandbox_can_mount_mediated_secret_socket_and_token():
    built = build_oci_command(
        image="registry.example/nexus-runtime@sha256:" + "a" * 64,
        artifact_path="/var/lib/nexus/artifacts/aa/bb/" + "b" * 64,
        entrypoint="plugin.run",
        max_memory_mb=512,
        cidfile="/var/lib/nexus/runtime/cid/test.cid",
        secret_socket_path="/var/lib/nexus/runtime/secrets/test.sock",
        secret_token_path="/var/lib/nexus/runtime/secrets/test.token",
    )
    joined = " ".join(built.command)
    assert "--network=none" in built.command
    assert "dst=/nexus/secrets.sock,readonly" in joined
    assert "dst=/nexus/secrets.token,readonly" in joined
    assert "--env=NEXUS_SECRET_SOCKET=/nexus/secrets.sock" in built.command
    assert "--env=NEXUS_SECRET_TOKEN_FILE=/nexus/secrets.token" in built.command

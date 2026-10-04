import pytest

from services.execution.sandbox import build_oci_command, validate_sandbox_image


def test_sandbox_image_must_be_digest_pinned():
    with pytest.raises(ValueError):
        validate_sandbox_image("python:3.12")


def test_sandbox_command_is_non_networked_and_read_only():
    built = build_oci_command(
        image="registry.example/nexus-runtime@sha256:" + "a" * 64,
        artifact_path="/var/lib/nexus/artifacts/aa/bb/" + "b" * 64,
        entrypoint="plugin.run",
        max_memory_mb=512,
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

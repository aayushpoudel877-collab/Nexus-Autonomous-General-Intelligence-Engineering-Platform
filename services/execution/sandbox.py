"""OCI sandbox command construction for the isolated execution launcher."""

from dataclasses import dataclass
import re


_IMAGE_DIGEST = re.compile(r"^[A-Za-z0-9./_-]+@sha256:[0-9a-f]{64}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_MAX_PIDS = 128
_TMPFS_SIZE = "64m"


@dataclass(frozen=True)
class SandboxCommand:
    command: list[str]
    image: str
    cidfile: str


def _absolute_path(value: str, *, label: str) -> str:
    normalized = value.strip()
    if not normalized or not normalized.startswith("/") or "\x00" in normalized:
        raise ValueError(f"{label} must be an absolute path")
    return normalized


def validate_sandbox_image(image: str) -> str:
    normalized = image.strip()
    if not _IMAGE_DIGEST.fullmatch(normalized):
        raise ValueError("Sandbox image must be pinned by a sha256 digest")
    return normalized


def build_oci_command(
    *,
    image: str,
    artifact_path: str,
    entrypoint: str,
    max_memory_mb: int,
    cidfile: str = "/tmp/nexus-sandbox.cid",
    docker_binary: str = "docker",
) -> SandboxCommand:
    if max_memory_mb < 64 or max_memory_mb > 4096:
        raise ValueError("Sandbox memory must be between 64 and 4096 MiB")
    image = validate_sandbox_image(image)
    artifact = _absolute_path(artifact_path, label="Artifact path")
    cidfile = _absolute_path(cidfile, label="Container ID file")
    binary = docker_binary.strip()
    if not binary or any(ch in binary for ch in ("\x00", "\n", "\r")):
        raise ValueError("Docker binary path is invalid")

    normalized_entrypoint = entrypoint.strip()
    if not normalized_entrypoint or any(
        ch in normalized_entrypoint for ch in ("\x00", "\n", "\r")
    ):
        raise ValueError("Sandbox entrypoint is invalid")

    command = [
        binary,
        "run",
        "--rm",
        "--init",
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=128",
        f"--memory={max_memory_mb}m",
        f"--memory-swap={max_memory_mb}m",
        "--cpus=1",
        "--ulimit=nofile=256:256",
        "--tmpfs",
        f"/tmp:rw,nosuid,nodev,noexec,size={_TMPFS_SIZE}",
        "--mount",
        f"type=bind,src={artifact},dst=/nexus/artifact,readonly",
        "--cidfile",
        cidfile,
        "--workdir=/nexus",
        image,
        normalized_entrypoint,
    ]
    return SandboxCommand(command=command, image=image, cidfile=cidfile)


def validate_artifact_digest(digest: str) -> str:
    normalized = digest.strip().lower()
    if not _DIGEST.fullmatch(normalized):
        raise ValueError("Artifact digest must be a SHA-256 hexadecimal value")
    return normalized

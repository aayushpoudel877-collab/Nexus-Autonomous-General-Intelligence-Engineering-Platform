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
    egress_socket_path: str | None = None,
    egress_token_path: str | None = None,
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
    if (egress_socket_path is None) != (egress_token_path is None):
        raise ValueError("Egress socket and token paths must be provided together")
    egress_mounts: list[str] = []
    egress_env: list[str] = []
    if egress_socket_path is not None and egress_token_path is not None:
        egress_socket = _absolute_path(egress_socket_path, label="Egress socket path")
        egress_token = _absolute_path(egress_token_path, label="Egress token path")
        egress_mounts = [
            "--mount",
            f"type=bind,src={egress_socket},dst=/nexus/egress.sock,readonly",
            "--mount",
            f"type=bind,src={egress_token},dst=/nexus/egress.token,readonly",
        ]
        egress_env = [
            "--env=NEXUS_EGRESS_SOCKET=/nexus/egress.sock",
            "--env=NEXUS_EGRESS_TOKEN_FILE=/nexus/egress.token",
        ]

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
        *egress_mounts,
        *egress_env,
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

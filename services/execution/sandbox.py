"""OCI sandbox command construction without shell interpolation or direct execution."""

from dataclasses import dataclass
import re


_IMAGE_DIGEST = re.compile(r"^[A-Za-z0-9./_-]+@sha256:[0-9a-f]{64}$")
_MAX_PIDS = 128
_TMPFS_SIZE = "64m"


@dataclass(frozen=True)
class SandboxCommand:
    command: list[str]
    image: str


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
) -> SandboxCommand:
    if max_memory_mb < 64 or max_memory_mb > 4096:
        raise ValueError("Sandbox memory must be between 64 and 4096 MiB")
    image = validate_sandbox_image(image)
    artifact = artifact_path.strip()
    if not artifact.startswith("/"):
        raise ValueError("Artifact path must be an absolute runtime path")
    normalized_entrypoint = entrypoint.strip()
    if not normalized_entrypoint or any(ch in normalized_entrypoint for ch in ("\x00", "\n", "\r")):
        raise ValueError("Sandbox entrypoint is invalid")

    command = [
        "docker",
        "run",
        "--rm",
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        f"--pids-limit={_MAX_PIDS}",
        f"--memory={max_memory_mb}m",
        "--cpus=1",
        "--tmpfs",
        f"/tmp:rw,nosuid,nodev,noexec,size={_TMPFS_SIZE}",
        "--mount",
        f"type=bind,src={artifact},dst=/nexus/artifact,readonly",
        "--workdir=/nexus",
        image,
        normalized_entrypoint,
    ]
    return SandboxCommand(command=command, image=image)

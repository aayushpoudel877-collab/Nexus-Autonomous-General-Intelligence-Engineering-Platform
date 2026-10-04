import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class NexusApiError(RuntimeError):
    status_code: int
    detail: Any

    def __str__(self) -> str:
        return f"NEXUS API request failed ({self.status_code}): {self.detail}"


class NexusClient:
    """Minimal dependency-free client for the Phase 10 developer API."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            url,
            data=data,
            method=method.upper(),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Nexus-API-Key": self.api_key,
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(raw)
            except json.JSONDecodeError:
                detail = raw or str(exc.reason)
            raise NexusApiError(exc.code, detail) from exc
        except URLError as exc:
            raise NexusApiError(0, str(exc.reason)) from exc

        if not raw:
            return None
        return json.loads(raw)

    def whoami(self) -> dict[str, Any]:
        return self.request("GET", "/developer/whoami")

    def list_plugins(self) -> list[dict[str, Any]]:
        return self.request("GET", "/developer/plugins")

    def create_plugin(
        self,
        *,
        slug: str,
        name: str,
        version: str,
        description: str = "",
        manifest: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            "/developer/plugins",
            {
                "slug": slug,
                "name": name,
                "version": version,
                "description": description,
                "manifest": manifest or {},
            },
        )



    def list_integrations(self) -> list[dict[str, Any]]:
        return self.request("GET", "/governance/integrations")

    def create_integration(
        self,
        *,
        provider: str,
        name: str,
        scopes: list[str] | None = None,
        config: dict[str, Any] | None = None,
        secret_ref: str | None = None,
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            "/governance/integrations",
            {
                "provider": provider,
                "name": name,
                "scopes": scopes or [],
                "config": config or {},
                "secret_ref": secret_ref,
            },
        )

    def list_plugin_releases(self, plugin_id: str) -> list[dict[str, Any]]:
        return self.request("GET", f"/governance/plugins/{plugin_id}/releases")

    def publish_plugin_release(
        self,
        plugin_id: str,
        *,
        version: str,
        artifact_uri: str,
        package_sha256: str,
        manifest_sha256: str,
        signature: str,
        signer: str,
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            f"/governance/plugins/{plugin_id}/releases",
            {
                "version": version,
                "artifact_uri": artifact_uri,
                "package_sha256": package_sha256,
                "manifest_sha256": manifest_sha256,
                "signature": signature,
                "signer": signer,
            },
        )

    def request_plugin_installation(
        self,
        plugin_release_id: str,
        requested_scopes: list[str] | None = None,
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            "/governance/plugin-installations",
            {
                "plugin_release_id": plugin_release_id,
                "requested_scopes": requested_scopes or [],
            },
        )



    def list_trust_roots(self) -> list[dict[str, Any]]:
        return self.request("GET", "/governance/trust-roots")

    def create_trust_root(
        self,
        *,
        key_id: str,
        name: str,
        public_key: str,
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            "/governance/trust-roots",
            {
                "key_id": key_id,
                "name": name,
                "algorithm": "ed25519",
                "public_key": public_key,
            },
        )

    def revoke_trust_root(self, trust_root_id: str) -> dict[str, Any]:
        return self.request("POST", f"/governance/trust-roots/{trust_root_id}/revoke")

    def verify_plugin_artifact(
        self,
        release_id: str,
        *,
        trust_root_id: str,
        artifact_base64: str,
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            f"/governance/plugin-releases/{release_id}/verify-artifact",
            {
                "trust_root_id": trust_root_id,
                "artifact_base64": artifact_base64,
            },
        )

    def list_execution_requests(self) -> list[dict[str, Any]]:
        return self.request("GET", "/execution/requests")

    def get_execution_request(self, request_id: str) -> dict[str, Any]:
        return self.request("GET", f"/execution/requests/{request_id}")

    def create_execution_request(
        self,
        *,
        installation_id: str,
        idempotency_key: str,
        entrypoint: str,
        capabilities: list[str],
        input_json: dict[str, Any] | None = None,
        timeout_seconds: int = 300,
        max_memory_mb: int = 512,
        max_output_bytes: int = 1_048_576,
        network_policy: str = "none",
        network_allowlist: list[str] | None = None,
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            "/execution/requests",
            {
                "installation_id": installation_id,
                "idempotency_key": idempotency_key,
                "entrypoint": entrypoint,
                "capabilities": capabilities,
                "input_json": input_json or {},
                "timeout_seconds": timeout_seconds,
                "max_memory_mb": max_memory_mb,
                "max_output_bytes": max_output_bytes,
                "network_policy": network_policy,
                "network_allowlist": network_allowlist or [],
            },
        )

    def cancel_execution_request(
        self,
        request_id: str,
        reason: str = "Cancelled by caller",
    ) -> dict[str, Any]:
        return self.request(
            "POST",
            f"/execution/requests/{request_id}/cancel",
            {"reason": reason},
        )

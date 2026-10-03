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

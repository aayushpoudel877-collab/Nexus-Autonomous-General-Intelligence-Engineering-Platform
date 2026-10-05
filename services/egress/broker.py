"""Authenticated, bounded HTTP(S) egress broker for isolated executions."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
from dataclasses import dataclass
import ipaddress
import json
from pathlib import Path
import re
import socket
import ssl
from typing import Any
from urllib.parse import urlsplit
import uuid


MAX_PROTOCOL_LINE_BYTES = 256 * 1024
MAX_HEADER_BYTES = 32 * 1024
MAX_HEADERS = 64
MAX_HEADER_VALUE_BYTES = 4 * 1024
MAX_METHOD_BYTES = 16
MAX_BODY_BYTES = 128 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_TIMEOUT_SECONDS = 15.0
MAX_CONCURRENT_REQUESTS = 4

_ALLOWED_METHODS = {"GET", "HEAD", "POST"}
_HEADER_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_FORBIDDEN_REQUEST_HEADERS = {
    "connection",
    "content-length",
    "host",
    "proxy-connection",
    "transfer-encoding",
}
_ALLOWED_SCHEMES = {"http", "https"}


class EgressPolicyError(ValueError):
    """Raised when an egress request violates the execution policy."""


@dataclass(frozen=True)
class EgressResult:
    status_code: int
    headers: dict[str, str]
    body: bytes
    truncated: bool


def _normalize_allowlist_entry(entry: str) -> tuple[str, int | None]:
    item = entry.strip().lower()
    if ":" in item:
        host, port_text = item.rsplit(":", 1)
        if port_text.isdigit():
            port = int(port_text)
            if 1 <= port <= 65_535:
                return host, port
    return item, None


def _is_global_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return address.is_global and not address.is_multicast


def _host_port_allowed(host: str, port: int, allowlist: list[str]) -> bool:
    for entry in allowlist:
        allowed_host, allowed_port = _normalize_allowlist_entry(entry)
        if host != allowed_host:
            continue
        if allowed_port is None:
            if port in {80, 443}:
                return True
        elif port == allowed_port:
            return True
    return False


async def _resolve_public_addresses(host: str, port: int) -> list[str]:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise EgressPolicyError("IP literals are not permitted in egress URLs")

    loop = asyncio.get_running_loop()
    infos = await loop.run_in_executor(
        None,
        lambda: socket.getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM,
        ),
    )
    addresses: list[str] = []
    for _family, _socktype, _proto, _canonname, sockaddr in infos:
        address = sockaddr[0]
        if not _is_global_ip(address):
            raise EgressPolicyError(
                "Egress destination resolved to a private, local or reserved address"
            )
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise EgressPolicyError("Egress destination did not resolve to a public address")
    return addresses


def _validate_headers(headers: Any) -> dict[str, str]:
    if headers is None:
        return {}
    if not isinstance(headers, dict) or len(headers) > MAX_HEADERS:
        raise EgressPolicyError("Egress headers must be a bounded JSON object")
    normalized: dict[str, str] = {}
    total = 0
    for raw_name, raw_value in headers.items():
        if not isinstance(raw_name, str) or not _HEADER_NAME.fullmatch(raw_name):
            raise EgressPolicyError("Egress request contains an invalid header name")
        if raw_name.lower() in _FORBIDDEN_REQUEST_HEADERS:
            raise EgressPolicyError(
                f"Egress request header '{raw_name}' is controlled by the broker"
            )
        if not isinstance(raw_value, str):
            raise EgressPolicyError("Egress header values must be strings")
        if any(ch in raw_value for ch in ("\x00", "\r", "\n")):
            raise EgressPolicyError("Egress header values cannot contain control characters")
        encoded_size = len(raw_value.encode("utf-8"))
        if encoded_size > MAX_HEADER_VALUE_BYTES:
            raise EgressPolicyError("Egress header value exceeds the broker limit")
        total += len(raw_name.encode("utf-8")) + encoded_size
        if total > MAX_HEADER_BYTES:
            raise EgressPolicyError("Egress request headers exceed the broker limit")
        normalized[raw_name] = raw_value
    return normalized


def _decode_body(value: Any) -> bytes:
    if value in (None, ""):
        return b""
    if not isinstance(value, str):
        raise EgressPolicyError("Egress request body must be base64 text")
    try:
        body = base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
        raise EgressPolicyError("Egress request body is not valid base64") from exc
    if len(body) > MAX_BODY_BYTES:
        raise EgressPolicyError("Egress request body exceeds the broker limit")
    return body


async def _read_http_headers(
    reader: asyncio.StreamReader,
) -> tuple[int, dict[str, str], bytes]:
    header_blob = await reader.readuntil(b"\r\n\r\n")
    if len(header_blob) > MAX_HEADER_BYTES:
        raise EgressPolicyError("Egress response headers exceed the broker limit")
    lines = header_blob[:-4].split(b"\r\n")
    if not lines:
        raise EgressPolicyError("Egress response did not contain a status line")
    try:
        version, status_text, _reason = lines[0].decode("iso-8859-1").split(" ", 2)
        status_code = int(status_text)
    except (ValueError, UnicodeDecodeError) as exc:
        raise EgressPolicyError("Egress response status line is invalid") from exc
    if not version.startswith("HTTP/"):
        raise EgressPolicyError("Egress response protocol is invalid")

    headers: dict[str, str] = {}
    for raw_line in lines[1:]:
        try:
            name, value = raw_line.decode("iso-8859-1").split(":", 1)
        except (ValueError, UnicodeDecodeError) as exc:
            raise EgressPolicyError("Egress response contained an invalid header") from exc
        name = name.strip().lower()
        value = value.strip()
        if not name or len(value.encode("utf-8")) > MAX_HEADER_VALUE_BYTES:
            raise EgressPolicyError("Egress response header is invalid")
        headers[name] = value
        if len(headers) > MAX_HEADERS:
            raise EgressPolicyError("Egress response contains too many headers")
    return status_code, headers, b""


async def _read_response_body(
    reader: asyncio.StreamReader,
    headers: dict[str, str],
    *,
    max_bytes: int,
    is_head: bool,
) -> tuple[bytes, bool]:
    if is_head:
        return b"", False

    transfer_encoding = headers.get("transfer-encoding", "").lower()
    if "chunked" in transfer_encoding:
        chunks: list[bytes] = []
        total = 0
        while True:
            line = await reader.readline()
            if not line:
                raise EgressPolicyError("Egress chunked response ended unexpectedly")
            try:
                size = int(line.split(b";", 1)[0].strip(), 16)
            except ValueError as exc:
                raise EgressPolicyError("Egress chunk size is invalid") from exc
            if size == 0:
                await reader.readuntil(b"\r\n")
                return b"".join(chunks), False
            if size > max_bytes - total:
                data = await reader.read(max_bytes - total + 1)
                return b"".join(chunks) + data[: max_bytes - total], True
            chunk = await reader.readexactly(size)
            await reader.readexactly(2)
            chunks.append(chunk)
            total += size

    content_length = headers.get("content-length")
    if content_length is not None:
        try:
            expected = int(content_length)
        except ValueError as exc:
            raise EgressPolicyError("Egress content length is invalid") from exc
        if expected < 0:
            raise EgressPolicyError("Egress content length is invalid")
        if expected > max_bytes:
            data = await reader.read(max_bytes + 1)
            return data[:max_bytes], True
        return await reader.readexactly(expected), False

    chunks = []
    total = 0
    while total <= max_bytes:
        chunk = await reader.read(min(64 * 1024, max_bytes - total + 1))
        if not chunk:
            return b"".join(chunks), False
        remaining = max_bytes - total
        if len(chunk) > remaining:
            chunks.append(chunk[:remaining])
            return b"".join(chunks), True
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks), True


async def perform_http_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes,
    allowlist: list[str],
    timeout_seconds: float,
    max_response_bytes: int,
) -> EgressResult:
    if method not in _ALLOWED_METHODS:
        raise EgressPolicyError("Egress method is not permitted")
    if len(method.encode("ascii")) > MAX_METHOD_BYTES:
        raise EgressPolicyError("Egress method is invalid")

    parsed = urlsplit(url)
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise EgressPolicyError("Only HTTP and HTTPS egress URLs are permitted")
    if parsed.username or parsed.password:
        raise EgressPolicyError("Egress URLs may not contain credentials")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or len(host) > 253:
        raise EgressPolicyError("Egress URL hostname is invalid")
    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise EgressPolicyError("Egress URL port is invalid") from exc
    if not _host_port_allowed(host, port, allowlist):
        raise EgressPolicyError("Egress destination is not present in the execution allowlist")

    addresses = await _resolve_public_addresses(host, port)
    request_headers = _validate_headers(headers)
    if len(body) > MAX_BODY_BYTES:
        raise EgressPolicyError("Egress request body exceeds the broker limit")

    target = parsed.path or "/"
    if parsed.query:
        target += "?" + parsed.query
    if any(ord(ch) < 0x20 for ch in target):
        raise EgressPolicyError("Egress URL contains invalid control characters")

    request_headers["Host"] = host if port in {80, 443} else f"{host}:{port}"
    request_headers["Connection"] = "close"
    request_headers["Content-Length"] = str(len(body))
    request_headers["Accept-Encoding"] = "identity"
    request_headers["User-Agent"] = "NEXUS-egress-broker/1"

    ssl_context = None
    if parsed.scheme.lower() == "https":
        ssl_context = ssl.create_default_context()

    last_error: Exception | None = None
    for address in addresses:
        writer: asyncio.StreamWriter | None = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    address,
                    port,
                    ssl=ssl_context,
                    server_hostname=host if ssl_context else None,
                ),
                timeout=timeout_seconds,
            )
            request_lines = [f"{method} {target} HTTP/1.1"]
            request_lines.extend(f"{name}: {value}" for name, value in request_headers.items())
            request_bytes = ("\r\n".join(request_lines) + "\r\n\r\n").encode("utf-8")
            writer.write(request_bytes + body)
            await asyncio.wait_for(writer.drain(), timeout=timeout_seconds)
            status_code, response_headers, _ = await asyncio.wait_for(
                _read_http_headers(reader),
                timeout=timeout_seconds,
            )
            response_body, truncated = await asyncio.wait_for(
                _read_response_body(
                    reader,
                    response_headers,
                    max_bytes=max_response_bytes,
                    is_head=method == "HEAD",
                ),
                timeout=timeout_seconds,
            )
            return EgressResult(
                status_code=status_code,
                headers=response_headers,
                body=response_body,
                truncated=truncated,
            )
        except EgressPolicyError:
            raise
        except (
            asyncio.TimeoutError,
            ConnectionError,
            OSError,
            ssl.SSLError,
            asyncio.IncompleteReadError,
        ) as exc:
            last_error = exc
        finally:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    pass

    raise EgressPolicyError("Egress destination could not be reached") from last_error


class EgressBroker:
    """Per-execution Unix-socket broker that mediates allowlisted HTTP(S) requests."""

    def __init__(
        self,
        *,
        allowlist: list[str],
        token: str,
        socket_path: str,
        request_timeout_seconds: float,
        max_request_bytes: int,
        max_response_bytes: int,
    ) -> None:
        if not token or any(ch in token for ch in ("\x00", "\r", "\n")):
            raise ValueError("Egress broker token is invalid")
        if not 1 <= max_request_bytes <= MAX_BODY_BYTES:
            raise ValueError("Egress request limit is outside the supported range")
        if not 1 <= max_response_bytes <= MAX_RESPONSE_BYTES:
            raise ValueError("Egress response limit is outside the supported range")
        if not 0.1 <= request_timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise ValueError("Egress timeout is outside the supported range")
        self.allowlist = list(allowlist)
        self.token = token
        self.socket_path = str(Path(socket_path))
        self.request_timeout_seconds = request_timeout_seconds
        self.max_request_bytes = max_request_bytes
        self.max_response_bytes = max_response_bytes
        self._server: asyncio.AbstractServer | None = None
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self._tasks: set[asyncio.Task[None]] = set()

    async def start(self) -> None:
        path = Path(self.socket_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=self.socket_path,
            limit=MAX_PROTOCOL_LINE_BYTES,
        )
        try:
            path.chmod(0o600)
        except OSError:
            await self.stop()
            raise

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        Path(self.socket_path).unlink(missing_ok=True)

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        task = asyncio.current_task()
        if task is not None:
            self._tasks.add(task)
        try:
            async with self._semaphore:
                await self._serve_request(reader, writer)
        finally:
            if task is not None:
                self._tasks.discard(task)
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    async def _serve_request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            raw = await reader.readuntil(b"\n")
            if len(raw) > MAX_PROTOCOL_LINE_BYTES:
                raise EgressPolicyError("Egress broker request is too large")
            request = json.loads(raw.decode("utf-8"))
            if not isinstance(request, dict):
                raise EgressPolicyError("Egress broker request must be a JSON object")
            token = request.get("token")
            if not isinstance(token, str) or not hmac.compare_digest(token, self.token):
                raise EgressPolicyError("Egress broker authentication failed")
            method = request.get("method", "GET")
            url = request.get("url", "")
            headers = request.get("headers", {})
            body = _decode_body(request.get("body_base64"))
            if len(raw) > self.max_request_bytes:
                raise EgressPolicyError("Egress broker request exceeds the configured limit")
            if not isinstance(method, str) or not isinstance(url, str):
                raise EgressPolicyError("Egress broker request method and URL are invalid")
            if not isinstance(headers, dict):
                raise EgressPolicyError("Egress broker headers are invalid")
            result = await perform_http_request(
                method=method.upper(),
                url=url,
                headers=headers,
                body=body,
                allowlist=self.allowlist,
                timeout_seconds=self.request_timeout_seconds,
                max_response_bytes=self.max_response_bytes,
            )
            response = {
                "ok": True,
                "status_code": result.status_code,
                "headers": result.headers,
                "body_base64": base64.b64encode(result.body).decode("ascii"),
                "truncated": result.truncated,
            }
        except (
            EgressPolicyError,
            json.JSONDecodeError,
            UnicodeDecodeError,
            asyncio.LimitOverrunError,
            asyncio.IncompleteReadError,
        ) as exc:
            response = {"ok": False, "error": str(exc)[:500]}
        except asyncio.CancelledError:
            raise
        except (
            OSError,
            ValueError,
            TypeError,
            ConnectionError,
            asyncio.TimeoutError,
            binascii.Error,
            ssl.SSLError,
        ):
            response = {"ok": False, "error": "Egress broker request failed"}
        writer.write((json.dumps(response, separators=(",", ":")) + "\n").encode("utf-8"))
        await writer.drain()


async def create_egress_broker(
    *,
    runtime_root: str,
    execution_id: str | None,
    allowlist: list[str],
    request_timeout_seconds: float,
    max_request_bytes: int,
    max_response_bytes: int,
) -> tuple[EgressBroker, str]:
    token = uuid.uuid4().hex + uuid.uuid4().hex
    execution_token = execution_id or uuid.uuid4().hex
    root = Path(runtime_root).resolve() / "egress"
    root.mkdir(parents=True, exist_ok=True)
    socket_path = root / f"{execution_token}.sock"
    token_path = root / f"{execution_token}.token"
    token_path.write_text(token, encoding="ascii")
    token_path.chmod(0o600)
    broker = EgressBroker(
        allowlist=allowlist,
        token=token,
        socket_path=str(socket_path),
        request_timeout_seconds=request_timeout_seconds,
        max_request_bytes=max_request_bytes,
        max_response_bytes=max_response_bytes,
    )
    await broker.start()
    return broker, str(token_path)

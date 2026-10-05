import asyncio
import json

import pytest

import services.egress.broker as broker_module
from services.egress.broker import (
    EgressBroker,
    EgressPolicyError,
    EgressResult,
    perform_http_request,
)


@pytest.mark.asyncio
async def test_broker_authenticates_requests_and_returns_structured_result(tmp_path, monkeypatch):
    async def fake_request(**_kwargs):
        return EgressResult(
            status_code=200,
            headers={"content-type": "text/plain"},
            body=b"hello",
            truncated=False,
        )

    monkeypatch.setattr(broker_module, "perform_http_request", fake_request)
    socket_path = tmp_path / "egress.sock"
    broker = EgressBroker(
        allowlist=["api.example.com:443"],
        token="secret-token",
        socket_path=str(socket_path),
        request_timeout_seconds=5,
        max_request_bytes=128 * 1024,
        max_response_bytes=4 * 1024 * 1024,
    )
    await broker.start()
    try:
        reader, writer = await asyncio.open_unix_connection(socket_path)
        writer.write(
            (
                json.dumps(
                    {
                        "token": "secret-token",
                        "method": "GET",
                        "url": "https://api.example.com/data",
                    }
                )
                + "\n"
            ).encode()
        )
        await writer.drain()
        response = json.loads((await reader.readline()).decode())
        writer.close()
        await writer.wait_closed()
        assert response["ok"] is True
        assert response["status_code"] == 200
        assert response["body_base64"] == "aGVsbG8="
    finally:
        await broker.stop()


@pytest.mark.asyncio
async def test_broker_rejects_bad_token(tmp_path, monkeypatch):
    async def fake_request(**_kwargs):
        raise AssertionError("upstream request should not be attempted")

    monkeypatch.setattr(broker_module, "perform_http_request", fake_request)
    socket_path = tmp_path / "egress.sock"
    broker = EgressBroker(
        allowlist=["api.example.com:443"],
        token="secret-token",
        socket_path=str(socket_path),
        request_timeout_seconds=5,
        max_request_bytes=128 * 1024,
        max_response_bytes=4 * 1024 * 1024,
    )
    await broker.start()
    try:
        reader, writer = await asyncio.open_unix_connection(socket_path)
        writer.write(
            (
                json.dumps(
                    {
                        "token": "wrong-token",
                        "method": "GET",
                        "url": "https://api.example.com/data",
                    }
                )
                + "\n"
            ).encode()
        )
        await writer.drain()
        response = json.loads((await reader.readline()).decode())
        writer.close()
        await writer.wait_closed()
        assert response["ok"] is False
        assert "authentication" in response["error"]
    finally:
        await broker.stop()


def test_allowlist_is_exact_host_and_port():
    assert broker_module._host_port_allowed(
        "api.example.com", 443, ["api.example.com:443"]
    )
    assert not broker_module._host_port_allowed(
        "api.example.com", 80, ["api.example.com:443"]
    )
    assert not broker_module._host_port_allowed(
        "other.example.com", 443, ["api.example.com:443"]
    )


def test_non_global_address_is_rejected():
    assert broker_module._is_global_ip("8.8.8.8") is True
    assert broker_module._is_global_ip("10.0.0.10") is False
    assert broker_module._is_global_ip("127.0.0.1") is False
    assert broker_module._is_global_ip("169.254.169.254") is False


@pytest.mark.asyncio
async def test_private_dns_result_is_rejected(monkeypatch):
    async def fake_getaddrinfo(*_args, **_kwargs):
        return [
            (
                2,
                1,
                6,
                "",
                ("10.0.0.10", 443),
            )
        ]

    monkeypatch.setattr(
        broker_module.socket,
        "getaddrinfo",
        fake_getaddrinfo,
    )
    with pytest.raises(EgressPolicyError):
        await broker_module._resolve_public_addresses("api.example.com", 443)


def test_broker_result_is_bounded():
    result = EgressResult(
        status_code=200,
        headers={"content-type": "text/plain"},
        body=b"ok",
        truncated=False,
    )
    assert result.body == b"ok"


@pytest.mark.asyncio
async def test_perform_http_request_pins_resolved_ip_and_parses_response(monkeypatch):
    seen = {}

    async def handle(reader, writer):
        request = await reader.readuntil(b"\r\n\r\n")
        seen["request"] = request.decode("iso-8859-1")
        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/plain\r\n"
            b"Content-Length: 5\r\n"
            b"Connection: close\r\n\r\n"
            b"hello"
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    async def fake_resolve(_host, _port):
        return ["127.0.0.1"]

    monkeypatch.setattr(broker_module, "_resolve_public_addresses", fake_resolve)
    try:
        result = await perform_http_request(
            method="GET",
            url=f"http://api.example.com:{port}/health",
            headers={"X-Test": "broker"},
            body=b"",
            allowlist=[f"api.example.com:{port}"],
            timeout_seconds=5,
            max_response_bytes=1024,
        )
    finally:
        server.close()
        await server.wait_closed()

    assert result.status_code == 200
    assert result.body == b"hello"
    assert result.truncated is False
    assert "GET /health HTTP/1.1" in seen["request"]
    assert "Host: api.example.com:" + str(port) in seen["request"]
    assert "X-Test: broker" in seen["request"]

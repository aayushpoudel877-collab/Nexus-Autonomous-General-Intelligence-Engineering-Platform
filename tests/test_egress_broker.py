[object Object]

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

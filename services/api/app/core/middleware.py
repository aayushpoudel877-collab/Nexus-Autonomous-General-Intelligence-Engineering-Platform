import re
import secrets

from fastapi import Request, Response

from .config import settings

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestBodyTooLarge(Exception):
    pass


def _request_id(request: Request) -> str:
    supplied = request.headers.get("X-Request-ID", "").strip()
    return supplied if _REQUEST_ID.fullmatch(supplied) else secrets.token_hex(16)


async def security_middleware(request: Request, call_next) -> Response:
    from fastapi.responses import JSONResponse

    content_length = request.headers.get("Content-Length")
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length"})
        if declared_length > settings.max_request_bytes:
            return JSONResponse(status_code=413, content={"detail": "Request body is too large"})
    origin = request.headers.get("Origin", "").strip()
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and origin and origin not in settings.cors_origin_list:
        return JSONResponse(status_code=403, content={"detail": "Origin is not allowed"})
    request_id = _request_id(request)
    request.state.request_id = request_id

    original_receive = request._receive
    received_bytes = 0

    async def limited_receive():
        nonlocal received_bytes
        message = await original_receive()
        if message["type"] == "http.request":
            received_bytes += len(message.get("body", b""))
            if received_bytes > settings.max_request_bytes:
                raise RequestBodyTooLarge
        return message

    request._receive = limited_receive
    try:
        response = await call_next(request)
    except RequestBodyTooLarge:
        return JSONResponse(status_code=413, content={"detail": "Request body is too large"})
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api/v1/auth/"):
        response.headers["Cache-Control"] = "no-store"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

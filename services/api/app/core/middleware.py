import re
import secrets

from fastapi import Request, Response

from .config import settings

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _request_id(request: Request) -> str:
    supplied = request.headers.get("X-Request-ID", "").strip()
    return supplied if _REQUEST_ID.fullmatch(supplied) else secrets.token_hex(16)


async def security_middleware(request: Request, call_next) -> Response:
    request_id = _request_id(request)
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

from uuid import uuid4
from services.api.app.core.security import create_access_token, decode_access_token, hash_password, verify_password

def test_password_hash_round_trip():
    password = "Nexus-test-password-123"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)

def test_access_token_round_trip():
    user_id = uuid4()
    token = create_access_token(user_id)
    assert decode_access_token(token) == user_id


def test_request_id_and_security_headers():
    from fastapi.testclient import TestClient
    from services.api.app.main import app

    response = TestClient(app).get("/api/v1/health", headers={"X-Request-ID": "req_123"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req_123"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_invalid_request_id_is_replaced():
    from fastapi.testclient import TestClient
    from services.api.app.main import app

    response = TestClient(app).get("/api/v1/health", headers={"X-Request-ID": "bad\r\nvalue"})
    value = response.headers["X-Request-ID"]
    assert value != "bad\r\nvalue"
    assert 1 <= len(value) <= 64


def test_security_headers_omit_hsts_in_development():
    from fastapi.testclient import TestClient
    from services.api.app.main import app

    response = TestClient(app).get("/api/v1/health")
    assert "Strict-Transport-Security" not in response.headers


def test_untrusted_cross_origin_state_change_is_rejected():
    from fastapi.testclient import TestClient
    from services.api.app.main import app

    response = TestClient(app).post(
        "/api/v1/auth/login",
        headers={"Origin": "https://evil.example"},
        json={"email": "someone@example.com", "password": "not-a-password"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Origin is not allowed"


def test_auth_responses_are_marked_no_store():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from services.api.app.core.middleware import security_middleware

    test_app = FastAPI()
    test_app.middleware("http")(security_middleware)

    @test_app.post("/api/v1/auth/test")
    def auth_probe():
        return {"status": "ok"}

    response = TestClient(test_app).post("/api/v1/auth/test")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"


def test_oversized_request_is_rejected_before_route_execution():
    from fastapi.testclient import TestClient
    from services.api.app.main import app

    response = TestClient(app).post(
        "/api/v1/auth/login",
        headers={"Content-Length": str(10_485_761)},
        content=b"x",
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "Request body is too large"


def test_invalid_content_length_is_rejected():
    from fastapi.testclient import TestClient
    from services.api.app.main import app

    response = TestClient(app).post(
        "/api/v1/auth/login",
        headers={"Content-Length": "not-a-number"},
        content=b"x",
    )
    assert response.status_code == 400

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

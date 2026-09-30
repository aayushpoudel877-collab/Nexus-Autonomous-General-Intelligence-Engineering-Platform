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

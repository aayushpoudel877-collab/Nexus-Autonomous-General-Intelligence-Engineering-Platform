import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID
import jwt
from pwdlib import PasswordHash
from ..core.config import settings

password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return password_hash.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)

def create_access_token(user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "type": "access", "iat": now, "exp": now + timedelta(minutes=settings.jwt_access_minutes)}
    return jwt.encode(payload, settings.nexus_secret_key, algorithm=ALGORITHM)

def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)

def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def decode_access_token(token: str) -> UUID:
    payload = jwt.decode(token, settings.nexus_secret_key, algorithms=[ALGORITHM])
    if payload.get("type") != "access" or not payload.get("sub"):
        raise jwt.InvalidTokenError("invalid token")
    return UUID(payload["sub"])

import hashlib
import json
import secrets


ALLOWED_API_KEY_SCOPES = frozenset(
    {
        "developer:read",
        "developer:write",
        "plugin:read",
        "plugin:write",
        "plugin:release",
        "plugin:install",
        "plugin:execute",
        "integration:read",
        "integration:write",
    }
)
DEFAULT_API_KEY_SCOPES = ("developer:read", "plugin:read", "integration:read")


def generate_api_key() -> tuple[str, str, str]:
    """Return the plaintext token, display prefix, and one-way digest."""
    token = f"nxk_{secrets.token_hex(6)}_{secrets.token_urlsafe(32)}"
    prefix = token.split("_", 2)[1]
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return token, prefix, digest


def hash_api_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_scopes(scopes: list[str] | tuple[str, ...] | None) -> list[str]:
    selected = list(dict.fromkeys(scopes or DEFAULT_API_KEY_SCOPES))
    invalid = sorted(set(selected) - ALLOWED_API_KEY_SCOPES)
    if invalid:
        raise ValueError(f"Unsupported API key scopes: {', '.join(invalid)}")
    if not selected:
        return list(DEFAULT_API_KEY_SCOPES)
    return selected



def is_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True



def canonical_manifest_sha256(manifest: dict) -> str:
    payload = json.dumps(
        manifest,
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

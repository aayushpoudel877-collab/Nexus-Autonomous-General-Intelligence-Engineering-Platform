from datetime import datetime, timezone
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models import DeveloperApiKey, Membership, Role, User
from ..services.ecosystem import hash_api_key
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = (
        credentials.credentials
        if credentials
        else request.cookies.get("nexus_access_token")
    )
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    try:
        user_id: UUID = decode_access_token(token)
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        ) from exc
    user = await db.scalar(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    selected_org = request.cookies.get("nexus_organization_id")
    if selected_org:
        try:
            setattr(user, "_selected_organization_id", UUID(selected_org))
        except ValueError:
            setattr(user, "_selected_organization_id", None)
    return user


async def get_membership(user: User, db: AsyncSession) -> Membership:
    """Resolve the selected membership, failing closed on ambiguity."""

    selected_id = getattr(user, "_selected_organization_id", None)
    if selected_id is not None:
        memberships = list(
            (
                await db.scalars(
                    select(Membership)
                    .where(Membership.user_id == user.id)
                )
            ).all()
        )
        for membership in memberships:
            if membership.organization_id == selected_id:
                return membership
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Selected organization is not available to this account",
        )

    memberships = list(
        (
            await db.scalars(
                select(Membership)
                .where(Membership.user_id == user.id)
                .order_by(Membership.organization_id)
            )
        ).all()
    )
    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No organization membership",
        )
    if len(memberships) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account belongs to multiple organizations; select an organization first",
        )
    return memberships[0]


def require_roles(*roles: str):
    async def dependency(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        membership = await get_membership(user, db)
        role = await db.scalar(select(Role).where(Role.id == membership.role_id))
        if not role or role.name not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return user

    return dependency



api_key_header = APIKeyHeader(name="X-Nexus-API-Key", auto_error=False)


async def get_developer_api_key(
    credentials: str | None = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> DeveloperApiKey:
    if not credentials or not credentials.startswith("nxk_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Developer API key required",
        )
    key = await db.scalar(
        select(DeveloperApiKey).where(DeveloperApiKey.key_hash == hash_api_key(credentials))
    )
    now = datetime.now(timezone.utc)
    if (
        not key
        or key.revoked_at is not None
        or (key.expires_at is not None and key.expires_at <= now)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired developer API key",
        )
    key.last_used_at = now
    await db.commit()
    return key


def require_api_key_scopes(*scopes: str):
    async def dependency(
        api_key: DeveloperApiKey = Depends(get_developer_api_key),
    ) -> DeveloperApiKey:
        missing = [scope for scope in scopes if scope not in (api_key.scopes or [])]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"message": "API key scope is insufficient", "missing": missing},
            )
        return api_key

    return dependency

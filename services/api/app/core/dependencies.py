from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models import Membership, Role, User
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
    return user


async def get_membership(user: User, db: AsyncSession) -> Membership:
    """Resolve the user's sole membership without silently choosing a tenant.

    Multi-organization selection is intentionally explicit work for a later phase.
    Until then, fail closed rather than accidentally operating in an arbitrary org.
    """
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
            detail=(
                "This account belongs to multiple organizations; "
                "explicit organization selection is not configured yet"
            ),
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

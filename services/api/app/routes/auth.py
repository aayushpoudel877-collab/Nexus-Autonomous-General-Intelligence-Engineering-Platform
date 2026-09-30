from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from ..core.config import settings
from ..core.dependencies import get_current_user
from ..core.security import create_access_token, create_refresh_token, hash_password, hash_refresh_token, verify_password
from ..db.session import get_db
from ..models import Membership, Organization, RefreshSession, Role, User
from ..schemas.auth import LoginRequest, MeResponse, RegisterRequest, TokenResponse, UserResponse
from ..services.audit import record_audit

router = APIRouter(tags=["auth"])

def _set_auth_cookies(response: Response, tokens: TokenResponse) -> None:
    secure = settings.is_production
    response.set_cookie("nexus_access_token", tokens.access_token, httponly=True, secure=secure, samesite="lax", max_age=settings.jwt_access_minutes * 60, path="/")
    response.set_cookie("nexus_refresh_token", tokens.refresh_token, httponly=True, secure=secure, samesite="lax", max_age=settings.jwt_refresh_days * 86400, path="/api/v1/auth")

async def _issue_tokens(db: AsyncSession, user: User) -> TokenResponse:
    refresh = create_refresh_token()
    db.add(RefreshSession(user_id=user.id, token_hash=hash_refresh_token(refresh), expires_at=datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_days)))
    return TokenResponse(access_token=create_access_token(user.id), refresh_token=refresh)

def _request_meta(request: Request) -> tuple[str | None, str | None]:
    return request.client.host if request.client else None, request.headers.get("user-agent")

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower()
    if await db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Email is already registered")
    role = await db.scalar(select(Role).where(Role.name == "owner"))
    if not role:
        role = Role(name="owner", description="Organization owner")
        db.add(role)
        await db.flush()
    slug = f"{payload.organization_name.lower().replace(' ', '-')}-{create_refresh_token()[:8]}"
    org = Organization(name=payload.organization_name, slug=slug)
    user = User(email=email, full_name=payload.full_name, password_hash=hash_password(payload.password))
    db.add_all([org, user])
    await db.flush()
    db.add(Membership(user_id=user.id, organization_id=org.id, role_id=role.id))
    ip, agent = _request_meta(request)
    await record_audit(db, action="identity.registered", resource_type="user", actor_user_id=user.id, organization_id=org.id, detail={"email": email}, ip_address=ip, user_agent=agent)
    tokens = await _issue_tokens(db, user)
    await db.commit()
    _set_auth_cookies(response, tokens)
    return tokens

@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower()
    user = await db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")
    membership = await db.scalar(select(Membership).where(Membership.user_id == user.id))
    ip, agent = _request_meta(request)
    await record_audit(db, action="identity.login", resource_type="user", actor_user_id=user.id, organization_id=membership.organization_id if membership else None, ip_address=ip, user_agent=agent)
    tokens = await _issue_tokens(db, user)
    await db.commit()
    _set_auth_cookies(response, tokens)
    return tokens

@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response, refresh_token: str | None = None, db: AsyncSession = Depends(get_db)):
    token = refresh_token or request.cookies.get("nexus_refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token required")
    session = await db.scalar(select(RefreshSession).where(RefreshSession.token_hash == hash_refresh_token(token)))
    now = datetime.now(timezone.utc)
    if not session or session.revoked_at or session.expires_at <= now:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    user = await db.get(User, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User is unavailable")
    session.revoked_at = now
    tokens = await _issue_tokens(db, user)
    await db.commit()
    _set_auth_cookies(response, tokens)
    return tokens

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, refresh_token: str | None = None, db: AsyncSession = Depends(get_db)):
    token = refresh_token or request.cookies.get("nexus_refresh_token")
    if token:
        session = await db.scalar(select(RefreshSession).where(RefreshSession.token_hash == hash_refresh_token(token)))
        if session and not session.revoked_at:
            session.revoked_at = datetime.now(timezone.utc)
            await db.commit()
    response.delete_cookie("nexus_access_token", path="/")
    response.delete_cookie("nexus_refresh_token", path="/api/v1/auth")

@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    membership = await db.scalar(select(Membership).where(Membership.user_id == user.id))
    if not membership:
        raise HTTPException(status_code=403, detail="No organization membership")
    role = await db.get(Role, membership.role_id)
    return MeResponse(user=UserResponse.model_validate(user), organization_id=membership.organization_id, role=role.name if role else "unknown")

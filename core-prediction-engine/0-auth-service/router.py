from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth_utils import (
    create_access_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from shared.config import settings
from shared.database import get_db
from shared.deps import get_current_admin, get_current_user
from shared.models import Fixture, Slip, User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordBody(BaseModel):
    email: EmailStr


class ResetPasswordBody(BaseModel):
    token: str = Field(min_length=10)
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    is_admin: bool = False

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MessageResponse(BaseModel):
    message: str
    reset_link: str | None = None


def _token_response(user: User) -> TokenResponse:
    token = create_access_token(str(user.id), user.email)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterBody, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=body.email.lower(), password_hash=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginBody, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    return _token_response(user)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(body: ForgotPasswordBody, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    message = "If that email exists, a reset link has been sent."

    if not user:
        return MessageResponse(message=message)

    raw_token = generate_reset_token()
    user.reset_token_hash = hash_reset_token(raw_token)
    user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await db.commit()

    reset_link = f"{settings.app_public_url.rstrip('/')}/reset-password?token={raw_token}"
    if settings.expose_password_reset_link:
        return MessageResponse(message=message, reset_link=reset_link)
    return MessageResponse(message=message)


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(body: ResetPasswordBody, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    token_hash = hash_reset_token(body.token)
    result = await db.execute(select(User).where(User.reset_token_hash == token_hash))
    user = result.scalar_one_or_none()
    if not user or not user.reset_token_expires_at:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    if user.reset_token_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user.password_hash = hash_password(body.new_password)
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    await db.commit()
    return MessageResponse(message="Password updated. You can log in now.")


admin_router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserOut(BaseModel):
    id: UUID
    email: str
    is_admin: bool
    is_active: bool
    created_at: datetime
    slip_count: int


class AdminOverview(BaseModel):
    users: int
    active_users: int
    admins: int
    fixtures: int
    slips: int


class UserActiveUpdate(BaseModel):
    is_active: bool


@admin_router.get("/overview", response_model=AdminOverview)
async def admin_overview(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> AdminOverview:
    users = await db.scalar(select(func.count()).select_from(User)) or 0
    active_users = await db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0
    admins = await db.scalar(select(func.count()).select_from(User).where(User.is_admin.is_(True))) or 0
    fixtures = await db.scalar(select(func.count()).select_from(Fixture)) or 0
    slips = await db.scalar(select(func.count()).select_from(Slip)) or 0
    return AdminOverview(
        users=users,
        active_users=active_users,
        admins=admins,
        fixtures=fixtures,
        slips=slips,
    )


@admin_router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> list[AdminUserOut]:
    counts = await db.execute(select(Slip.user_id, func.count()).group_by(Slip.user_id))
    slip_counts = {user_id: count for user_id, count in counts.all()}
    result = await db.execute(select(User).order_by(User.created_at))
    return [
        AdminUserOut(
            id=user.id,
            email=user.email,
            is_admin=user.is_admin,
            is_active=user.is_active,
            created_at=user.created_at,
            slip_count=slip_counts.get(user.id, 0),
        )
        for user in result.scalars().all()
    ]


@admin_router.patch("/users/{user_id}", response_model=AdminUserOut)
async def set_user_active(
    user_id: UUID,
    body: UserActiveUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> AdminUserOut:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id and not body.is_active:
        raise HTTPException(status_code=400, detail="You cannot disable your own admin account")
    user.is_active = body.is_active
    await db.commit()
    await db.refresh(user)
    slip_count = await db.scalar(select(func.count()).select_from(Slip).where(Slip.user_id == user.id)) or 0
    return AdminUserOut(
        id=user.id,
        email=user.email,
        is_admin=user.is_admin,
        is_active=user.is_active,
        created_at=user.created_at,
        slip_count=slip_count,
    )

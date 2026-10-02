"""Create the local admin account used for user control and operator tools."""

from sqlalchemy import select

from shared.auth_utils import hash_password, verify_password
from shared.config import settings
from shared.database import SessionLocal
from shared.models import User


async def ensure_admin_account() -> None:
    email = settings.admin_email.strip().lower()
    if not email or not settings.admin_password:
        return

    async with SessionLocal() as db:
        stale = await db.execute(select(User).where(User.email == "admin@casuya.local"))
        leftover = stale.scalar_one_or_none()
        if leftover:
            await db.delete(leftover)
            await db.commit()

        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            changed = False
            if not user.is_admin:
                user.is_admin = True
                changed = True
            if not verify_password(settings.admin_password, user.password_hash):
                user.password_hash = hash_password(settings.admin_password)
                changed = True
            if changed:
                await db.commit()
            return

        db.add(
            User(
                email=email,
                password_hash=hash_password(settings.admin_password),
                is_admin=True,
                is_active=True,
            )
        )
        await db.commit()

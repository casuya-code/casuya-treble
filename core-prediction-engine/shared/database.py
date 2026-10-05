from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from shared.config import settings

engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from shared import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "ALTER TABLE slips ADD COLUMN IF NOT EXISTS user_id UUID "
                "REFERENCES users(id) ON DELETE CASCADE"
            )
        )
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_slips_user_id ON slips (user_id)"))
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE")
        )
        await conn.execute(
            text("ALTER TABLE slips ADD COLUMN IF NOT EXISTS forced BOOLEAN NOT NULL DEFAULT FALSE")
        )
        await conn.execute(text("ALTER TABLE fixtures ADD COLUMN IF NOT EXISTS home_corners INTEGER"))
        await conn.execute(text("ALTER TABLE fixtures ADD COLUMN IF NOT EXISTS away_corners INTEGER"))
        await conn.execute(text("ALTER TABLE fixtures ADD COLUMN IF NOT EXISTS fh_corner_over_25 DOUBLE PRECISION"))
        await conn.execute(text("ALTER TABLE fixtures ADD COLUMN IF NOT EXISTS fh_corner_over_35 DOUBLE PRECISION"))
        await conn.execute(text("ALTER TABLE fixtures ADD COLUMN IF NOT EXISTS sportradar_id VARCHAR(32)"))
        await conn.execute(text("ALTER TABLE fixtures ADD COLUMN IF NOT EXISTS fh_corners INTEGER"))
        await conn.execute(
            text(
                "ALTER TABLE fixtures ADD COLUMN IF NOT EXISTS fh_half_complete BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )

    if engine.dialect.name != "postgresql":
        return
    autocommit = engine.execution_options(isolation_level="AUTOCOMMIT")
    async with autocommit.connect() as conn:
        for label in ("T00_06", "T06_12", "T12_18", "T18_24", "ALL_DAY"):
            await conn.execute(text(f"ALTER TYPE time_category ADD VALUE IF NOT EXISTS '{label}'"))

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.models import Slip


async def purge_old_slips(db: AsyncSession) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.purge_days)
    result = await db.execute(delete(Slip).where(Slip.timestamp < cutoff))
    await db.commit()
    return result.rowcount or 0

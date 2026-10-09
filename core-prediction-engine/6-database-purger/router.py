from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.database import get_db
from shared.purger import purge_old_basketball_runs, purge_old_slips

router = APIRouter(prefix="/maintenance", tags=["database-purger"])


class PurgeResult(BaseModel):
    deleted_slips: int
    retention_days: int


class BasketballPurgeResult(BaseModel):
    deleted_gate_runs: int
    retention_days: int


@router.post("/purge-slips", response_model=PurgeResult)
async def purge_slips(db: AsyncSession = Depends(get_db)) -> PurgeResult:
    deleted = await purge_old_slips(db)
    return PurgeResult(deleted_slips=deleted, retention_days=settings.purge_days)


@router.post("/purge-basketball", response_model=BasketballPurgeResult)
async def purge_basketball(db: AsyncSession = Depends(get_db)) -> BasketballPurgeResult:
    deleted = await purge_old_basketball_runs(db)
    return BasketballPurgeResult(deleted_gate_runs=deleted, retention_days=settings.purge_days)

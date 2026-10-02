from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.models import Fixture, MatchStatus
from shared.schemas import FixtureOut, LiveScoreUpdate
from shared.tracker_logic import recompute_all_slip_statuses

router = APIRouter(prefix="/tracker", tags=["realtime-tracker"])


@router.patch("/fixtures/{fixture_id}/live", response_model=FixtureOut)
async def update_live_score(
    fixture_id: UUID, payload: LiveScoreUpdate, db: AsyncSession = Depends(get_db)
) -> Fixture:
    fixture = await db.get(Fixture, fixture_id)
    if not fixture:
        raise HTTPException(status_code=404, detail="Fixture not found")

    fixture.home_goals = payload.home_goals
    fixture.away_goals = payload.away_goals
    fixture.status = payload.status
    if payload.status == MatchStatus.FINISHED:
        fixture.status = MatchStatus.FINISHED

    await db.commit()
    await db.refresh(fixture)
    await recompute_all_slip_statuses(db)
    return fixture


@router.post("/fixtures/{fixture_id}/kickoff", response_model=FixtureOut)
async def mark_kickoff(fixture_id: UUID, db: AsyncSession = Depends(get_db)) -> Fixture:
    fixture = await db.get(Fixture, fixture_id)
    if not fixture:
        raise HTTPException(status_code=404, detail="Fixture not found")
    fixture.status = MatchStatus.LIVE
    fixture.home_goals = fixture.home_goals or 0
    fixture.away_goals = fixture.away_goals or 0
    await db.commit()
    await db.refresh(fixture)
    await recompute_all_slip_statuses(db)
    return fixture


@router.post("/fixtures/promote-scheduled", response_model=dict)
async def promote_due_fixtures(db: AsyncSession = Depends(get_db)) -> dict:
    """Demo helper: mark scheduled fixtures whose kickoff passed as LIVE."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Fixture).where(Fixture.status == MatchStatus.SCHEDULED, Fixture.kickoff_at <= now)
    )
    rows = list(result.scalars().all())
    for row in rows:
        row.status = MatchStatus.LIVE
        row.home_goals = row.home_goals or 0
        row.away_goals = row.away_goals or 0
    await db.commit()
    await recompute_all_slip_statuses(db)
    return {"promoted": len(rows)}

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.database import get_db
from shared.deps import get_current_user
from shared.models import Fixture, Slip, SlipLeg, SlipStatus, TimeCategory, User
from shared.poisson import edge_vs_market
from shared.schemas import SlipLegOut, SlipOut, SlipPlacedUpdate
from shared.slip_format import (
    average_leg_edge,
    build_betpawa_copy,
    combined_decimal_odds,
    slip_implied_win_probability,
)
from shared.config import settings
from shared.fixture_source import is_demo_fixture, prefer_real_fixtures, upcoming_fixtures
from shared.practice_cleanup import purge_practice_if_real_loaded
from shared.tracker_logic import recompute_all_slip_statuses, recompute_slip_statuses_for_user
from shared.treble_generator import find_best_trebles

router = APIRouter(prefix="/slips", tags=["slip-generator"])


def _slip_to_out(slip: Slip, fixtures_by_id: dict[UUID, Fixture]) -> SlipOut:
    legs_out: list[SlipLegOut] = []
    for leg in slip.legs:
        fx = fixtures_by_id[leg.fixture_id]
        legs_out.append(
            SlipLegOut(
                fixture_id=leg.fixture_id,
                home_team=fx.home_team,
                away_team=fx.away_team,
                league=fx.league,
                kickoff_at=fx.kickoff_at,
                market=leg.market,
                leg_odds=leg.leg_odds,
                model_probability=leg.model_probability,
                edge=edge_vs_market(leg.model_probability, leg.leg_odds),
                is_demo=is_demo_fixture(fx),
            )
        )
    combined = combined_decimal_odds([leg.leg_odds for leg in slip.legs])
    implied = slip_implied_win_probability(combined)
    avg_edge = average_leg_edge(
        [leg.model_probability for leg in slip.legs],
        [leg.leg_odds for leg in slip.legs],
    )
    return SlipOut(
        slip_id=slip.slip_id,
        time_category=slip.time_category,
        model_probability=slip.model_probability,
        closing_odds=combined,
        implied_probability=round(implied, 4),
        edge=round(avg_edge, 4) if avg_edge is not None else None,
        status=slip.status,
        placed_on_betpawa=slip.placed_on_betpawa,
        timestamp=slip.timestamp,
        legs=legs_out,
        betpawa_copy_text=build_betpawa_copy(slip, fixtures_by_id),
    )


@router.post("/generate", response_model=list[SlipOut])
async def generate_slips(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    min_odds: float = Query(3.0, ge=2.0, le=10.0),
    category: TimeCategory | None = Query(None),
    max_slips: int = Query(1, ge=1, le=10),
    replace_pending: bool = Query(True),
) -> list[SlipOut]:
    if replace_pending:
        pending = await db.execute(
            select(Slip.slip_id).where(Slip.status == SlipStatus.PENDING, Slip.user_id == user.id)
        )
        pending_ids = [row[0] for row in pending.all()]
        if pending_ids:
            await db.execute(delete(Slip).where(Slip.slip_id.in_(pending_ids)))
            await db.commit()

    result = await db.execute(select(Fixture).order_by(Fixture.kickoff_at))
    all_fixtures = list(result.scalars().all())
    fixtures = prefer_real_fixtures(upcoming_fixtures(all_fixtures))
    trebles = find_best_trebles(fixtures, min_combined_odds=min_odds, time_category=category, limit=max_slips)

    created: list[Slip] = []
    for treble in trebles:
        combined = combined_decimal_odds([leg.odds for leg in treble.legs])
        slip = Slip(
            user_id=user.id,
            time_category=treble.time_category,
            model_probability=round(treble.model_probability, 6),
            closing_odds=combined,
            status=SlipStatus.PENDING,
        )
        for leg in treble.legs:
            slip.legs.append(
                SlipLeg(
                    fixture_id=leg.fixture_id,
                    leg_odds=leg.odds,
                    model_probability=round(leg.model_probability, 6),
                )
            )
        db.add(slip)
        created.append(slip)

    await db.commit()
    for slip in created:
        await db.refresh(slip, attribute_names=["legs"])

    fixtures_by_id = {f.id: f for f in fixtures}
    out = [_slip_to_out(s, fixtures_by_id) for s in created]
    out.sort(key=lambda s: s.model_probability, reverse=True)
    return out


class RetentionInfo(BaseModel):
    retention_days: int


@router.get("/retention", response_model=RetentionInfo)
async def slip_retention_window() -> RetentionInfo:
    return RetentionInfo(retention_days=settings.purge_days)


@router.get("", response_model=list[SlipOut])
async def list_slips(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    category: TimeCategory | None = Query(None),
    status: SlipStatus | None = Query(None),
    days: int = Query(
        settings.purge_days,
        ge=1,
        le=settings.purge_days,
        description="Slips created within this many days (max retention window)",
    ),
) -> list[SlipOut]:
    await purge_practice_if_real_loaded(db)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = (
        select(Slip)
        .options(selectinload(Slip.legs))
        .where(Slip.user_id == user.id, Slip.timestamp >= cutoff)
    )
    if category:
        query = query.where(Slip.time_category == category)
    if status:
        query = query.where(Slip.status == status)
    result = await db.execute(query.order_by(Slip.timestamp.desc()))
    slips = list(result.scalars().unique().all())
    fixture_ids = {leg.fixture_id for slip in slips for leg in slip.legs}
    if not fixture_ids:
        return []
    fx_result = await db.execute(select(Fixture).where(Fixture.id.in_(fixture_ids)))
    fixtures_by_id = {f.id: f for f in fx_result.scalars().all()}
    status_rank = {SlipStatus.PENDING: 0, SlipStatus.LIVE: 1, SlipStatus.WON: 2, SlipStatus.LOST: 3}
    out: list[SlipOut] = []
    for slip in slips:
        if not slip.legs:
            continue
        if any(leg.fixture_id not in fixtures_by_id for leg in slip.legs):
            continue
        out.append(_slip_to_out(slip, fixtures_by_id))
    out.sort(key=lambda s: (status_rank.get(s.status, 9), -s.model_probability))
    return out


@router.delete("/pending", response_model=dict)
async def clear_pending_slips(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    result = await db.execute(
        delete(Slip).where(Slip.status == SlipStatus.PENDING, Slip.user_id == user.id)
    )
    await db.commit()
    return {"deleted": result.rowcount or 0}


@router.patch("/{slip_id}/placed", response_model=SlipOut)
async def mark_placed_on_betpawa(
    slip_id: UUID,
    payload: SlipPlacedUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SlipOut:
    result = await db.execute(
        select(Slip).options(selectinload(Slip.legs)).where(Slip.slip_id == slip_id, Slip.user_id == user.id)
    )
    slip = result.scalar_one_or_none()
    if not slip:
        raise HTTPException(status_code=404, detail="Slip not found")
    slip.placed_on_betpawa = payload.placed_on_betpawa
    await db.commit()
    await db.refresh(slip, attribute_names=["legs"])
    fixture_ids = [leg.fixture_id for leg in slip.legs]
    fx_result = await db.execute(select(Fixture).where(Fixture.id.in_(fixture_ids)))
    fixtures_by_id = {f.id: f for f in fx_result.scalars().all()}
    return _slip_to_out(slip, fixtures_by_id)


class SyncResponse(BaseModel):
    slips_updated: int


@router.post("/sync-status", response_model=SyncResponse)
async def sync_slip_statuses(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)) -> SyncResponse:
    count = await recompute_slip_statuses_for_user(db, user.id)
    return SyncResponse(slips_updated=count)


class PublicHistoryOut(BaseModel):
    stake: int
    matches_won: int
    matches_lost: int
    matches_pending: int
    trebles_placed: int
    trebles_won: int
    trebles_lost: int
    trebles_pending: int
    single_profit: float
    treble_profit: float
    days: list[dict]
    slips: list[dict]


@router.get("/history", response_model=PublicHistoryOut)
async def public_placed_history(db: AsyncSession = Depends(get_db)) -> PublicHistoryOut:
    """Placed treble results. No login. Stake of 2,000 on each match, and 2,000 on each treble."""
    from shared.fixture_source import is_demo_fixture
    from shared.models import MatchStatus
    from shared.public_history import HistoryLeg, HistorySlip, build_public_history

    await recompute_all_slip_statuses(db)
    result = await db.execute(
        select(Slip).options(selectinload(Slip.legs)).where(Slip.placed_on_betpawa.is_(True))
    )
    slips = list(result.scalars().unique().all())
    fixture_ids = {leg.fixture_id for slip in slips for leg in slip.legs}
    fixtures_by_id: dict[UUID, Fixture] = {}
    if fixture_ids:
        fx_result = await db.execute(select(Fixture).where(Fixture.id.in_(fixture_ids)))
        fixtures_by_id = {row.id: row for row in fx_result.scalars().all()}

    built = []
    for slip in slips:
        legs = []
        for leg in slip.legs:
            fixture = fixtures_by_id.get(leg.fixture_id)
            if fixture is None:
                continue
            legs.append(
                HistoryLeg(
                    fixture_id=str(fixture.id),
                    home_team=fixture.home_team,
                    away_team=fixture.away_team,
                    kickoff_at=fixture.kickoff_at,
                    odds=leg.leg_odds,
                    home_goals=fixture.home_goals,
                    away_goals=fixture.away_goals,
                    finished=fixture.status == MatchStatus.FINISHED,
                    practice=is_demo_fixture(fixture),
                )
            )
        if legs:
            built.append(HistorySlip(slip_id=str(slip.slip_id), placed_at=slip.timestamp, legs=legs))

    report = build_public_history(built)
    return PublicHistoryOut(**report)

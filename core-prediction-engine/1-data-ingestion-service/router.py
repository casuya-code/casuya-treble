import asyncio
import logging
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.betpawa_client import (
    BetPawaError,
    fetch_event_payload,
    fetch_football_over_15,
    sportradar_match_id,
)
from shared.config import settings
from shared.corners import LINE_FIELD
from shared.database import get_db
from shared.football_data import HistoricalSeedResult, ensure_historical_scores, import_football_data
from shared.league_names import league_key
from shared.models import Fixture
from shared.practice_cleanup import purge_practice_data
from shared.schemas import FixtureCreate, FixtureOut

logger = logging.getLogger("casuya.ingestion")

router = APIRouter(prefix="/ingestion", tags=["data-ingestion"])

NAIROBI = ZoneInfo("Africa/Nairobi")


def _set_corner_prices(fixture: Fixture, prices: dict[str, float]) -> None:
    """First-half corner Over prices, keyed by line. Never blanks a price already held."""
    for line, odds in prices.items():
        field = LINE_FIELD.get(line)
        if field and odds is not None and odds > 1.0:
            setattr(fixture, field, float(odds))


async def _store_sportradar_ids(db, external_ids: list[str]) -> None:
    """Attach the Sportradar widget id used to read the live corner timeline.

    Corner prices do not come from here: the event page carries no markets, so
    the list view is the only place they are quoted.
    """
    if not external_ids:
        return
    result = await db.execute(select(Fixture).where(Fixture.external_id.in_(external_ids)))
    fixtures = list(result.scalars())
    gate = asyncio.Semaphore(5)

    async def one(fixture: Fixture) -> None:
        event_id = (fixture.external_id or "").split(":", 1)[-1]
        async with gate:
            try:
                payload = await fetch_event_payload(event_id)
            except BetPawaError:
                logger.warning("event payload unavailable for %s", fixture.external_id)
                return
        if payload is None:
            return
        match_id = sportradar_match_id(payload)
        if match_id:
            fixture.sportradar_id = match_id

    await asyncio.gather(*[one(fixture) for fixture in fixtures])
    await db.commit()


class BetPawaSourceStatus(BaseModel):
    configured: bool = True
    brand: str
    base_url: str
    verify_url: str = "https://www.betpawa.co.tz/events/popular"


class BetPawaImportResult(BaseModel):
    imported: int
    updated: int
    skipped_no_market: int
    events_fetched: int
    practice_removed: int
    history_imported: int = 0
    history_updated: int = 0


class HistoricalImportResult(BaseModel):
    imported: int
    updated: int
    files: int
    skipped: bool = False


@router.get("/betpawa/status", response_model=BetPawaSourceStatus)
async def betpawa_source_status() -> BetPawaSourceStatus:
    return BetPawaSourceStatus(
        brand=settings.betpawa_brand,
        base_url=settings.betpawa_base_url,
    )


@router.post("/import/betpawa", response_model=BetPawaImportResult)
async def import_from_betpawa(
    db: AsyncSession = Depends(get_db),
    take: int | None = Query(default=None, ge=10, le=100),
    popular_only: bool = Query(False, description="Limit to BetPawa popular football list"),
) -> BetPawaImportResult:
    try:
        rows = await fetch_football_over_15(take=take, popular_only=popular_only)
    except BetPawaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    practice_removed = await purge_practice_data(db)

    imported = 0
    updated = 0
    for row in rows:
        result = await db.execute(select(Fixture).where(Fixture.external_id == row.external_id))
        fixture = result.scalar_one_or_none()
        if fixture:
            fixture.home_team = row.home_team
            fixture.away_team = row.away_team
            fixture.league = row.league
            fixture.kickoff_at = row.kickoff_at
            if fixture.opening_odds_over_15 is None:
                fixture.opening_odds_over_15 = row.decimal_odds
            fixture.closing_odds_over_15 = row.decimal_odds
            _set_corner_prices(fixture, row.fh_corner_overs)
            updated += 1
        else:
            new_fixture = Fixture(
                external_id=row.external_id,
                home_team=row.home_team,
                away_team=row.away_team,
                league=row.league,
                kickoff_at=row.kickoff_at,
                opening_odds_over_15=row.decimal_odds,
                closing_odds_over_15=row.decimal_odds,
                lambda_home=1.4,
                lambda_away=1.1,
            )
            _set_corner_prices(new_fixture, row.fh_corner_overs)
            db.add(new_fixture)
            imported += 1

    await db.commit()
    try:
        await _store_sportradar_ids(db, [row.external_id for row in rows if league_key(row.league)])
    except Exception:
        logger.exception("sportradar id fetch failed")
        await db.rollback()
    history = HistoricalSeedResult()
    try:
        history = await ensure_historical_scores(db)
    except Exception:
        logger.exception("historical score seed failed")
        await db.rollback()
    return BetPawaImportResult(
        imported=imported,
        updated=updated,
        skipped_no_market=0,
        events_fetched=len(rows),
        practice_removed=practice_removed,
        history_imported=history.imported,
        history_updated=history.updated,
    )


@router.post("/import/football-data", response_model=HistoricalImportResult)
async def import_historical_scores(db: AsyncSession = Depends(get_db)) -> HistoricalImportResult:
    """Load finished league scores used to rate attack and defence."""
    try:
        history = await import_football_data(db)
    except Exception as exc:
        logger.exception("historical score seed failed")
        await db.rollback()
        raise HTTPException(status_code=503, detail="Historical scores are unavailable") from exc
    return HistoricalImportResult(
        imported=history.imported,
        updated=history.updated,
        files=history.files,
        skipped=history.skipped,
    )


def _demo_fixtures() -> list[FixtureCreate]:
    # Practice only — fixed future date (not today's real schedule). One Nairobi date so they can form a treble.
    practice_day = datetime(2099, 6, 15, tzinfo=NAIROBI).date()
    kickoff_hours = (14, 15, 16, 17, 13, 12)
    samples = [
        ("Demo Arsenal", "Demo Brighton", "Practice — not a real match", 1.65, 1.05, 1.52),
        ("Demo Barcelona", "Demo Getafe", "Practice — not a real match", 1.85, 0.75, 1.48),
        ("Demo Bayern", "Demo Augsburg", "Practice — not a real match", 2.1, 0.85, 1.55),
        ("Demo Inter", "Demo Empoli", "Practice — not a real match", 1.75, 0.9, 1.5),
        ("Demo PSG", "Demo Lorient", "Practice — not a real match", 2.0, 0.7, 1.46),
        ("Demo Sporting", "Demo Estoril", "Practice — not a real match", 1.9, 0.95, 1.58),
    ]
    out: list[FixtureCreate] = []
    for i, (home, away, league, lh, la, odds) in enumerate(samples):
        kickoff = datetime.combine(practice_day, time(kickoff_hours[i], 0), tzinfo=NAIROBI).astimezone(
            timezone.utc
        )
        out.append(
            FixtureCreate(
                home_team=home,
                away_team=away,
                league=league,
                kickoff_at=kickoff,
                lambda_home=lh,
                lambda_away=la,
                opening_odds_over_15=round(odds + 0.03, 2),
                closing_odds_over_15=odds,
                external_id=f"demo-{home.lower().replace(' ', '-')}-{away.lower().replace(' ', '-')}",
            )
        )
    return out


@router.post("/fixtures", response_model=FixtureOut, status_code=201)
async def ingest_fixture(payload: FixtureCreate, db: AsyncSession = Depends(get_db)) -> Fixture:
    row = Fixture(**payload.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.post("/fixtures/seed-demo", response_model=list[FixtureOut])
async def seed_demo_fixtures(db: AsyncSession = Depends(get_db)) -> list[Fixture]:
    synced: list[Fixture] = []
    for item in _demo_fixtures():
        result = await db.execute(select(Fixture).where(Fixture.external_id == item.external_id))
        row = result.scalar_one_or_none()
        if row:
            row.home_team = item.home_team
            row.away_team = item.away_team
            row.league = item.league
            row.kickoff_at = item.kickoff_at
            row.lambda_home = item.lambda_home
            row.lambda_away = item.lambda_away
            row.opening_odds_over_15 = item.opening_odds_over_15
            row.closing_odds_over_15 = item.closing_odds_over_15
        else:
            row = Fixture(**item.model_dump())
            db.add(row)
        synced.append(row)
    await db.commit()
    for row in synced:
        await db.refresh(row)
    return synced


@router.get("/fixtures", response_model=list[FixtureOut])
async def list_fixtures(db: AsyncSession = Depends(get_db)) -> list[Fixture]:
    result = await db.execute(select(Fixture).order_by(Fixture.kickoff_at))
    return list(result.scalars().all())

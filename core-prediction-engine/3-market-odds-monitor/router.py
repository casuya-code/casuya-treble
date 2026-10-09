from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.database import get_db
from shared.deps import get_current_admin, get_current_user
from shared.models import Fixture, User
from shared.odds_api_client import OddsApiError, fetch_soccer_over_15
from shared.poisson import edge_vs_market, implied_probability, prob_over_15
from shared.schemas import FixtureOut

router = APIRouter(prefix="/odds", tags=["market-odds"])


class OddsUpdate(BaseModel):
    closing_odds_over_15: float = Field(ge=1.01, le=20.0)


class OddsSnapshot(BaseModel):
    fixture_id: UUID
    opening_odds: float | None
    closing_odds: float | None
    implied_closing: float | None
    model_probability: float
    edge: float | None


class OddsApiStatus(BaseModel):
    configured: bool
    default_sport: str
    default_region: str
    docs_url: str = "https://the-odds-api.com/liveapi/guides/v4/"


class OddsImportResult(BaseModel):
    imported: int
    updated: int
    skipped_no_market: int
    requests_remaining: str
    requests_used: str


@router.get("/provider/status", response_model=OddsApiStatus)
async def odds_provider_status() -> OddsApiStatus:
    return OddsApiStatus(
        configured=settings.odds_api_configured,
        default_sport=settings.odds_default_sport,
        default_region=settings.odds_default_region,
    )


@router.post("/import/the-odds-api", response_model=OddsImportResult)
async def import_from_the_odds_api(
    db: AsyncSession = Depends(get_db),
    sport: str | None = Query(None),
    region: str | None = Query(None),
    _user: User = Depends(get_current_user),
) -> OddsImportResult:
    try:
        rows, usage = await fetch_soccer_over_15(sport_key=sport, region=region)
    except OddsApiError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    imported = 0
    updated = 0
    for row in rows:
        result = await db.execute(select(Fixture).where(Fixture.external_id == row.external_id))
        fixture = result.scalar_one_or_none()
        if fixture:
            if fixture.opening_odds_over_15 is None:
                fixture.opening_odds_over_15 = row.decimal_odds
            fixture.closing_odds_over_15 = row.decimal_odds
            fixture.kickoff_at = row.commence_time
            updated += 1
        else:
            fixture = Fixture(
                external_id=row.external_id,
                home_team=row.home_team,
                away_team=row.away_team,
                league=row.sport_key.replace("_", " ").title(),
                kickoff_at=row.commence_time,
                opening_odds_over_15=row.decimal_odds,
                closing_odds_over_15=row.decimal_odds,
                lambda_home=1.4,
                lambda_away=1.1,
            )
            db.add(fixture)
            imported += 1

    await db.commit()
    return OddsImportResult(
        imported=imported,
        updated=updated,
        skipped_no_market=0,
        requests_remaining=usage.get("requests_remaining", "?"),
        requests_used=usage.get("requests_used", "?"),
    )


@router.patch("/fixtures/{fixture_id}/closing", response_model=FixtureOut)
async def update_closing_odds(
    fixture_id: UUID,
    payload: OddsUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> Fixture:
    fixture = await db.get(Fixture, fixture_id)
    if not fixture:
        raise HTTPException(status_code=404, detail="Fixture not found")
    if fixture.opening_odds_over_15 is None:
        fixture.opening_odds_over_15 = payload.closing_odds_over_15
    fixture.closing_odds_over_15 = payload.closing_odds_over_15
    await db.commit()
    await db.refresh(fixture)
    return fixture


@router.get("/fixtures/{fixture_id}/snapshot", response_model=OddsSnapshot)
async def odds_snapshot(fixture_id: UUID, db: AsyncSession = Depends(get_db)) -> OddsSnapshot:
    fixture = await db.get(Fixture, fixture_id)
    if not fixture:
        raise HTTPException(status_code=404, detail="Fixture not found")
    model_p = prob_over_15(fixture.lambda_home, fixture.lambda_away)
    closing = fixture.closing_odds_over_15
    return OddsSnapshot(
        fixture_id=fixture.id,
        opening_odds=fixture.opening_odds_over_15,
        closing_odds=closing,
        implied_closing=round(implied_probability(closing), 4) if closing else None,
        model_probability=round(model_p, 4),
        edge=round(edge_vs_market(model_p, closing), 4) if closing else None,
    )

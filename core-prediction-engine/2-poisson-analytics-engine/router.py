from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.models import Fixture
from shared.poisson import edge_vs_market, fair_odds_from_probability, implied_probability, prob_over_15
from shared.schemas import ProbabilityOut

router = APIRouter(prefix="/analytics", tags=["poisson-analytics"])


def _probability_row(fixture: Fixture) -> ProbabilityOut:
    model_p = prob_over_15(fixture.lambda_home, fixture.lambda_away)
    odds = fixture.closing_odds_over_15 or fixture.opening_odds_over_15
    implied = implied_probability(odds) if odds else None
    edge = edge_vs_market(model_p, odds) if odds else None
    return ProbabilityOut(
        fixture_id=fixture.id,
        market="Over 1.5 Goals",
        model_probability=round(model_p, 4),
        implied_probability=round(implied, 4) if implied is not None else None,
        edge=round(edge, 4) if edge is not None else None,
        fair_odds=fair_odds_from_probability(model_p),
    )


@router.get("/fixtures/{fixture_id}/over-15", response_model=ProbabilityOut)
async def get_over_15_probability(fixture_id: UUID, db: AsyncSession = Depends(get_db)) -> ProbabilityOut:
    fixture = await db.get(Fixture, fixture_id)
    if not fixture:
        raise HTTPException(status_code=404, detail="Fixture not found")
    return _probability_row(fixture)


@router.get("/fixtures/over-15/batch", response_model=list[ProbabilityOut])
async def batch_over_15(db: AsyncSession = Depends(get_db)) -> list[ProbabilityOut]:
    result = await db.execute(select(Fixture).order_by(Fixture.kickoff_at))
    return [_probability_row(f) for f in result.scalars().all()]

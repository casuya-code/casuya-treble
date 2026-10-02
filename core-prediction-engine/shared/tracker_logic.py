from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.models import Fixture, MatchStatus, Slip, SlipStatus
from shared.poisson import leg_won_over_15


def slip_status_from_fixtures(fixtures: list[Fixture]) -> SlipStatus:
    if not fixtures:
        return SlipStatus.PENDING

    outcomes: list[str] = []
    for fixture in fixtures:
        if fixture.home_goals is None or fixture.away_goals is None:
            outcomes.append("pending")
        elif leg_won_over_15(fixture.home_goals, fixture.away_goals):
            outcomes.append("won")
        elif fixture.status == MatchStatus.FINISHED:
            outcomes.append("lost")
        else:
            outcomes.append("pending")

    if any(outcome == "lost" for outcome in outcomes):
        return SlipStatus.LOST
    if all(outcome == "won" for outcome in outcomes):
        return SlipStatus.WON
    if any(fixture.status == MatchStatus.LIVE for fixture in fixtures):
        return SlipStatus.LIVE
    return SlipStatus.PENDING


async def recompute_all_slip_statuses(db: AsyncSession) -> int:
    result = await db.execute(select(Slip).options(selectinload(Slip.legs)))
    slips = list(result.scalars().unique().all())
    if not slips:
        return 0

    fixture_ids = {leg.fixture_id for slip in slips for leg in slip.legs}
    fx_result = await db.execute(select(Fixture).where(Fixture.id.in_(fixture_ids)))
    fixtures_by_id = {f.id: f for f in fx_result.scalars().all()}

    updated = 0
    for slip in slips:
        fixtures = [fixtures_by_id[leg.fixture_id] for leg in slip.legs]
        new_status = slip_status_from_fixtures(fixtures)
        if slip.status != new_status:
            slip.status = new_status
            updated += 1

    await db.commit()
    return updated


async def recompute_slip_statuses_for_user(db: AsyncSession, user_id: UUID) -> int:
    result = await db.execute(
        select(Slip).options(selectinload(Slip.legs)).where(Slip.user_id == user_id)
    )
    slips = list(result.scalars().unique().all())
    if not slips:
        return 0

    fixture_ids = {leg.fixture_id for slip in slips for leg in slip.legs}
    fx_result = await db.execute(select(Fixture).where(Fixture.id.in_(fixture_ids)))
    fixtures_by_id = {f.id: f for f in fx_result.scalars().all()}

    updated = 0
    for slip in slips:
        fixtures = [fixtures_by_id[leg.fixture_id] for leg in slip.legs]
        new_status = slip_status_from_fixtures(fixtures)
        if slip.status != new_status:
            slip.status = new_status
            updated += 1

    await db.commit()
    return updated

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.models import Fixture, MatchStatus, Slip, SlipStatus
from shared.poisson import leg_won_over_15


def fixtures_for_legs(legs, fixtures_by_id: dict) -> list[Fixture] | None:
    """Every leg's match, or None when one match was deleted."""
    found: list[Fixture] = []
    for leg in legs:
        fixture = fixtures_by_id.get(leg.fixture_id)
        if fixture is None:
            return None
        found.append(fixture)
    return found


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
    if not fixture_ids:
        return 0
    fx_result = await db.execute(select(Fixture).where(Fixture.id.in_(fixture_ids)))
    fixtures_by_id = {f.id: f for f in fx_result.scalars().all()}

    updated = 0
    for slip in slips:
        fixtures = fixtures_for_legs(slip.legs, fixtures_by_id)
        if fixtures is None:
            continue
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
    if not fixture_ids:
        return 0
    fx_result = await db.execute(select(Fixture).where(Fixture.id.in_(fixture_ids)))
    fixtures_by_id = {f.id: f for f in fx_result.scalars().all()}

    updated = 0
    for slip in slips:
        fixtures = fixtures_for_legs(slip.legs, fixtures_by_id)
        if fixtures is None:
            continue
        new_status = slip_status_from_fixtures(fixtures)
        if slip.status != new_status:
            slip.status = new_status
            updated += 1

    await db.commit()
    return updated

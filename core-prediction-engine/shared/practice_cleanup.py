"""Remove practice (demo) fixtures and any trebles built from them."""

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.fixture_source import DEMO_EXTERNAL_PREFIX
from shared.models import Fixture, Slip, SlipLeg


def _not_demo():
    prefix = f"{DEMO_EXTERNAL_PREFIX}%"
    return or_(Fixture.external_id.is_(None), ~Fixture.external_id.like(prefix))


async def has_real_fixtures(db: AsyncSession) -> bool:
    result = await db.execute(select(Fixture.id).where(_not_demo()).limit(1))
    return result.scalar_one_or_none() is not None


async def purge_practice_data(db: AsyncSession) -> int:
    """Delete demo fixtures and slips that use them. Returns fixtures removed."""
    demo = await db.execute(
        select(Fixture.id).where(Fixture.external_id.like(f"{DEMO_EXTERNAL_PREFIX}%"))
    )
    fixture_ids = [row[0] for row in demo.all()]
    if not fixture_ids:
        return 0

    slip_rows = await db.execute(select(SlipLeg.slip_id).where(SlipLeg.fixture_id.in_(fixture_ids)))
    slip_ids = list({row[0] for row in slip_rows.all()})
    if slip_ids:
        await db.execute(delete(Slip).where(Slip.slip_id.in_(slip_ids)))
    await db.execute(delete(Fixture).where(Fixture.id.in_(fixture_ids)))
    return len(fixture_ids)


async def purge_practice_if_real_loaded(db: AsyncSession) -> int:
    if not await has_real_fixtures(db):
        return 0
    removed = await purge_practice_data(db)
    if removed:
        await db.commit()
    return removed

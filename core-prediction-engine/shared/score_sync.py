"""Pull BetPawa scores onto stored matches and settle slips."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.betpawa_client import BetPawaError, fetch_event_score
from shared.models import Fixture, MatchStatus, SlipLeg
from shared.tracker_logic import recompute_all_slip_statuses

logger = logging.getLogger("casuya.scores")

_lock = asyncio.Lock()
_last_sync = 0.0
_MIN_GAP_SECONDS = 25


async def sync_betpawa_scores(db: AsyncSession, *, force: bool = False) -> int:
    """Update kicked-off BetPawa matches that are still open. Skips a burst of calls."""
    global _last_sync
    now_mono = time.monotonic()
    if not force and now_mono - _last_sync < _MIN_GAP_SECONDS:
        return 0
    if _lock.locked():
        return 0

    async with _lock:
        _last_sync = time.monotonic()
        moment = datetime.now(timezone.utc)
        result = await db.execute(
            select(Fixture)
            .join(SlipLeg, SlipLeg.fixture_id == Fixture.id)
            .where(
                Fixture.external_id.like("betpawa:%"),
                Fixture.status != MatchStatus.FINISHED,
                Fixture.kickoff_at <= moment,
            )
            .distinct()
        )
        fixtures = list(result.scalars().unique().all())
        if not fixtures:
            return 0

        async def one(fixture: Fixture):
            event_id = (fixture.external_id or "").split(":", 1)[1]
            try:
                score = await fetch_event_score(event_id)
            except BetPawaError:
                logger.warning("score fetch failed for %s", fixture.external_id)
                return fixture, None
            return fixture, score

        try:
            pairs = await asyncio.wait_for(asyncio.gather(*[one(row) for row in fixtures]), timeout=25)
        except TimeoutError:
            logger.warning("score refresh timed out")
            return 0
        updated = 0
        for fixture, score in pairs:
            if score is None:
                continue
            fixture.home_goals = score.home_goals
            fixture.away_goals = score.away_goals
            fixture.status = MatchStatus.LIVE if score.live else MatchStatus.FINISHED
            updated += 1
        if updated:
            await db.commit()
            await recompute_all_slip_statuses(db)
        return updated


async def score_refresh_loop() -> None:
    from shared.database import SessionLocal

    while True:
        await asyncio.sleep(45)
        try:
            async with SessionLocal() as db:
                await sync_betpawa_scores(db)
        except Exception:
            logger.exception("score refresh failed")

"""Pull BetPawa scores onto stored matches and settle slips."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.betpawa_client import BetPawaError, fetch_event_payload, parse_event_score, sportradar_match_id
from shared.corner_results import fetch_first_half_corners
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
        fixtures = {row.id: row for row in result.scalars().unique().all()}
        corner_rows = await db.execute(
            select(Fixture)
            .join(SlipLeg, SlipLeg.fixture_id == Fixture.id)
            .where(
                Fixture.external_id.like("betpawa:%"),
                Fixture.kickoff_at <= moment,
                SlipLeg.market.contains("Corner"),
                or_(Fixture.fh_half_complete.is_(False), Fixture.fh_half_complete.is_(None)),
            )
            .distinct()
        )
        corner_ids = set()
        for row in corner_rows.scalars().unique().all():
            fixtures[row.id] = row
            corner_ids.add(row.id)
        if not fixtures:
            return 0

        async def one(fixture: Fixture):
            event_id = (fixture.external_id or "").split(":", 1)[1]
            payload = None
            if fixture.status != MatchStatus.FINISHED or not fixture.sportradar_id:
                try:
                    payload = await fetch_event_payload(event_id)
                except BetPawaError:
                    logger.warning("score fetch failed for %s", fixture.external_id)
            score = parse_event_score(payload) if payload and fixture.status != MatchStatus.FINISHED else None
            match_id = sportradar_match_id(payload) if payload else None
            match_id = match_id or fixture.sportradar_id
            corners = None
            if fixture.id in corner_ids and match_id and not fixture.fh_half_complete:
                try:
                    corners = await fetch_first_half_corners(match_id)
                except Exception:
                    logger.warning("corner fetch failed for %s", fixture.external_id)
            return fixture, score, match_id, corners

        try:
            pairs = await asyncio.wait_for(asyncio.gather(*[one(row) for row in fixtures.values()]), timeout=25)
        except TimeoutError:
            logger.warning("score refresh timed out")
            return 0
        updated = 0
        for fixture, score, match_id, corners in pairs:
            if match_id and fixture.sportradar_id != match_id:
                fixture.sportradar_id = match_id
                updated += 1
            if score is not None:
                fixture.home_goals = score.home_goals
                fixture.away_goals = score.away_goals
                fixture.status = MatchStatus.LIVE if score.live else MatchStatus.FINISHED
                updated += 1
            if corners is not None:
                count, half_done = corners
                fixture.fh_corners = count
                fixture.fh_half_complete = half_done
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

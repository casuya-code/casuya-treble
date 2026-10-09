"""Background loop that evaluates the basketball slate on a fixed cadence."""

from __future__ import annotations

import asyncio
import logging

from shared.config import settings

logger = logging.getLogger("casuya.basketball")


async def basketball_scan_loop() -> None:
    if not settings.bb_enabled:
        logger.info("basketball scan loop disabled (bb_enabled=false)")
        return

    from shared.database import SessionLocal
    from shared.basketball.service import run_scan

    await asyncio.sleep(15)  # let the gateway finish booting first
    while True:
        stats: dict = {}
        try:
            async with SessionLocal() as db:
                stats = await run_scan(db)
            logger.info(
                "basketball scan: slate=%s evaluated=%s passed=%s locked=%s live=%s errors=%s",
                stats.get("slate"),
                stats.get("evaluated"),
                stats.get("passed"),
                stats.get("locked"),
                stats.get("live"),
                stats.get("errors"),
            )
        except Exception:  # noqa: BLE001 - keep the loop alive no matter what
            logger.exception("basketball scan failed")
        # Poll faster while a game is in progress so live scores stay fresh.
        minutes = settings.bb_live_scan_minutes if stats.get("live") else settings.bb_scan_minutes
        await asyncio.sleep(max(1, minutes) * 60)

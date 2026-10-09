"""Router 7 — basketball Absolute Intersect Filter (/btips)."""

from __future__ import annotations

import asyncio
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.basketball.absolute_filter import GATE_CATALOG
from shared.basketball.service import LAST_SCAN, audit, backfill, run_scan, shadow_backtest, shadow_record
from shared.config import settings
from shared.database import get_db
from shared.deps import get_current_admin, get_current_user
from shared.models import BBGame, BBGateRun, BBLineSnapshot, BBTip, User

router = APIRouter(prefix="/btips", tags=["basketball-filter"])

NAIROBI = "Africa/Nairobi"

BACKFILL_JOB: dict[str, Any] = {"state": "idle"}
_BACKFILL_TASK: asyncio.Task | None = None


def _nairobi_today() -> str:
    from zoneinfo import ZoneInfo

    return datetime.now(timezone.utc).astimezone(ZoneInfo(NAIROBI)).date().isoformat()


async def _game_payload(db: AsyncSession, game: BBGame, include_checks: bool = True) -> dict[str, Any]:
    run = (
        await db.execute(
            select(BBGateRun)
            .where(BBGateRun.game_id == game.id)
            .order_by(BBGateRun.ran_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    tip = (
        await db.execute(select(BBTip).where(BBTip.game_id == game.id))
    ).scalar_one_or_none()
    market = (
        await db.execute(
            select(BBLineSnapshot)
            .where(BBLineSnapshot.game_id == game.id)
            .order_by(BBLineSnapshot.captured_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    payload: dict[str, Any] = {
        "id": str(game.id),
        "espn_event_id": game.espn_event_id,
        "tipoff_at": game.tipoff_at.isoformat(),
        "home_team": game.home_team,
        "away_team": game.away_team,
        "status": game.status,
        "home_score": game.home_score,
        "away_score": game.away_score,
        "model": None,
        "market_total": market.over_under if market is not None else None,
        "result": None,
        "gate_run": None,
        "tip": None,
    }
    if (
        game.status == "post"
        and game.home_score is not None
        and game.away_score is not None
        and market is not None
    ):
        total = game.home_score + game.away_score
        if total > market.over_under:
            payload["result"] = "over"
        elif total < market.over_under:
            payload["result"] = "under"
        else:
            payload["result"] = "push"
    if run is not None:
        checks = dict(run.checks or {})
        payload["model"] = {
            "total": run.model_total,
            "p_over": run.p_over,
            "edge": run.edge,
        }
        payload["gate_run"] = {
            "passed": run.passed,
            "passed_count": sum(1 for c in checks.values() if isinstance(c, dict) and c.get("passed")),
            "ran_at": run.ran_at.isoformat(),
            "checks": checks if include_checks else None,
        }
    if tip is not None:
        payload["tip"] = {
            "id": str(tip.id),
            "status": tip.status,
            "pick": tip.pick,
            "line": tip.line,
            "over_odds": tip.over_odds,
            "model_total": tip.model_total,
            "p_over": tip.p_over,
            "edge": tip.edge,
            "created_at": tip.created_at.isoformat(),
            "settled_at": tip.settled_at.isoformat() if tip.settled_at else None,
            "notes": tip.notes,
        }
    return payload


@router.get("/health")
async def health(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    today = _nairobi_today()
    from zoneinfo import ZoneInfo

    nai_now = datetime.now(timezone.utc).astimezone(ZoneInfo(NAIROBI))
    nai_day_start = nai_now.replace(hour=0, minute=0, second=0, microsecond=0)
    nai_day_end = nai_day_start + timedelta(days=1)
    games_today = len(
        (
            await db.execute(
                select(BBGame.id).where(
                    BBGame.tipoff_at >= nai_day_start.astimezone(timezone.utc),
                    BBGame.tipoff_at < nai_day_end.astimezone(timezone.utc),
                )
            )
        ).all()
    )
    pending = len(
        (await db.execute(select(BBTip.id).where(BBTip.status == "PENDING"))).all()
    )
    return {
        "status": "ok",
        "enabled": settings.bb_enabled,
        "date": today,
        "games_today": games_today,
        "pending_tips": pending,
        "last_scan_at": LAST_SCAN.get("at"),
        "last_scan_stats": LAST_SCAN.get("stats"),
        "lock_minutes": settings.bb_lock_minutes,
        "scan_minutes": settings.bb_scan_minutes,
        "backfill": BACKFILL_JOB.get("state"),
    }


@router.get("/gates")
async def gates(_user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "gates": list(GATE_CATALOG),
        "policy": "strict boolean AND — any failing gate means AUTOMATED_REJECTION",
    }


@router.get("/games")
async def games_for_date(
    date: date_type | None = Query(default=None),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from zoneinfo import ZoneInfo

    target = date or datetime.now(timezone.utc).astimezone(ZoneInfo(NAIROBI)).date()
    tz = ZoneInfo(NAIROBI)
    start = datetime(target.year, target.month, target.day, tzinfo=tz)
    end = start + timedelta(days=1)
    rows = (
        await db.execute(
            select(BBGame)
            .where(
                BBGame.tipoff_at >= start.astimezone(timezone.utc),
                BBGame.tipoff_at < end.astimezone(timezone.utc),
            )
            .order_by(BBGame.tipoff_at.asc())
        )
    ).scalars().all()
    payloads = [await _game_payload(db, game) for game in rows]
    return {"date": target.isoformat(), "count": len(payloads), "games": payloads}


@router.get("/tips")
async def list_tips(
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    query = select(BBGame, BBTip).join(BBTip, BBTip.game_id == BBGame.id)
    if status:
        query = query.where(BBTip.status == status)
    rows = (
        await db.execute(query.order_by(BBGame.tipoff_at.desc()).limit(limit))
    ).all()
    items = []
    for game, tip in rows:
        payload = await _game_payload(db, game, include_checks=False)
        items.append(payload)
    return {"count": len(items), "items": items}


@router.get("/audit")
async def hit_rate(
    window_days: int = Query(default=30, ge=1, le=365),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await audit(db, window_days)


@router.get("/backtest")
async def backtest_rules(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Read-only what-if replay scoring candidate rules on history."""
    return await shadow_backtest(db)


@router.get("/shadow")
async def shadow_paper_record(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Read-only paper record for candidate rules on finished evaluated games."""
    return await shadow_record(db)


@router.post("/scan")
async def force_scan(
    _admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await run_scan(db, manual=True)


@router.post("/backfill")
async def start_backfill(
    seasons: str | None = Query(default=None, description="comma-separated ESPN season years"),
    max_games: int | None = Query(default=None, ge=1, le=5000),
    _admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    global _BACKFILL_TASK
    if BACKFILL_JOB.get("state") == "running":
        raise HTTPException(status_code=409, detail="backfill already running")
    parsed_seasons = [
        int(part)
        for part in (seasons or settings.bb_history_seasons).split(",")
        if part.strip().isdigit()
    ]
    if not parsed_seasons:
        raise HTTPException(status_code=400, detail="no valid seasons requested")

    from shared.database import SessionLocal

    BACKFILL_JOB.clear()
    BACKFILL_JOB.update({"state": "queued", "seasons": parsed_seasons})

    async def _run() -> None:
        async with SessionLocal() as db:
            await backfill(db, parsed_seasons, max_games or settings.bb_backfill_max_games, BACKFILL_JOB)

    _BACKFILL_TASK = asyncio.create_task(_run())
    return {"queued": True, "seasons": parsed_seasons, "max_games": max_games or settings.bb_backfill_max_games}


@router.get("/backfill/status")
async def backfill_status(_admin: User = Depends(get_current_admin)) -> dict[str, Any]:
    return BACKFILL_JOB

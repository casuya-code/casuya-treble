"""Orchestration for the basketball Absolute Intersect Filter.

run_scan() discovers the NBA slate, keeps history loaded, evaluates every
unlocked game through the ten strict gates, persists gate runs and tips, and
settles finished games. backfill() pulls a full season of schedules + lines.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.basketball import backtest, model, shadow
from shared.basketball.absolute_filter import (
    AbsoluteFilterReport,
    GameContext,
    Thresholds,
    evaluate,
)
from shared.basketball.espn_client import ESPNClient, ESPNError
from shared.basketball.filters import (
    FinishedGame,
    back_to_back,
    h2h_pace,
    over_rate,
    top_usage_and_rim,
    aggregate_players,
)
from shared.basketball.ingest import (
    ParsedSummary,
    ingest_events,
    ingest_summary,
    ingest_team_schedule,
)
from shared.config import settings
from shared.models import (
    BBGame,
    BBGateRun,
    BBLineSnapshot,
    BBPlayerGameStat,
    BBTip,
)

logger = logging.getLogger("casuya.basketball")

ET = ZoneInfo("America/New_York")

# Operational state shared with the router (read-only for the API layer).
LAST_SCAN: dict = {"at": None, "stats": None}
_SCHEDULE_REFRESH_SECONDS = 6 * 3600
_schedule_seen: dict[tuple[str, int], float] = {}

# Injury statuses that still count as "confirmed playing".
CLEAR_STATUSES = {"INJURY_STATUS_AVAILABLE"}


def season_years() -> list[int]:
    return [
        int(part)
        for part in settings.bb_history_seasons.split(",")
        if part.strip().isdigit()
    ]


async def _latest_lines(db: AsyncSession, game_ids: list[str]) -> dict[str, float]:
    """Newest known total per game id (rate inputs)."""
    if not game_ids:
        return {}
    rows = (
        await db.execute(
            select(BBLineSnapshot.game_id, BBLineSnapshot.over_under, BBLineSnapshot.captured_at)
            .where(BBLineSnapshot.game_id.in_(game_ids))
            .order_by(BBLineSnapshot.captured_at.asc())
        )
    ).all()
    latest: dict[str, float] = {}
    for game_id, total, _captured in rows:
        latest[str(game_id)] = float(total)
    return latest


async def _finished_team_games(
    db: AsyncSession,
    team_id: str,
    *,
    tipoff_before: datetime | None = None,
    season_types: tuple[int, ...] = (2,),
    limit: int = 220,
) -> list[FinishedGame]:
    """Finished games for a team with their newest known line attached."""
    now = datetime.now(timezone.utc)
    upper = tipoff_before or now
    rows = (
        await db.execute(
            select(BBGame)
            .where(
                (BBGame.home_team_id == team_id) | (BBGame.away_team_id == team_id),
                BBGame.status == "post",
                BBGame.season_type.in_(season_types),
                BBGame.home_score.is_not(None),
                BBGame.away_score.is_not(None),
                BBGame.tipoff_at < upper,
            )
            .order_by(BBGame.tipoff_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    lines = await _latest_lines(db, [str(g.id) for g in rows])
    return [
        FinishedGame(
            tipoff=g.tipoff_at,
            home_team_id=g.home_team_id,
            away_team_id=g.away_team_id,
            home_score=int(g.home_score),
            away_score=int(g.away_score),
            line=lines.get(str(g.id)),
            season_type=g.season_type,
        )
        for g in rows
    ]


async def _h2h_games(db: AsyncSession, team_a: str, team_b: str) -> list[FinishedGame]:
    rows = (
        await db.execute(
            select(BBGame)
            .where(
                BBGame.status == "post",
                BBGame.season_type == 2,
                BBGame.home_score.is_not(None),
                BBGame.away_score.is_not(None),
                (
                    ((BBGame.home_team_id == team_a) & (BBGame.away_team_id == team_b))
                    | ((BBGame.home_team_id == team_b) & (BBGame.away_team_id == team_a))
                ),
            )
            .order_by(BBGame.tipoff_at.desc())
            .limit(settings.bb_h2h_window + 5)
        )
    ).scalars().all()
    return [
        FinishedGame(
            tipoff=g.tipoff_at,
            home_team_id=g.home_team_id,
            away_team_id=g.away_team_id,
            home_score=int(g.home_score),
            away_score=int(g.away_score),
            line=None,
            season_type=g.season_type,
        )
        for g in rows
    ]


async def _last_finished(db: AsyncSession, team_id: str, before: datetime) -> BBGame | None:
    return (
        await db.execute(
            select(BBGame)
            .where(
                (BBGame.home_team_id == team_id) | (BBGame.away_team_id == team_id),
                BBGame.status == "post",
                BBGame.tipoff_at < before,
            )
            .order_by(BBGame.tipoff_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _team_player_rows(db: AsyncSession, team_id: str) -> list[tuple[str, str, int, int]]:
    """(athlete_id, name, points, blocks) over the team's newest finished reg games."""
    game_ids = [
        str(g)
        for g in (
            await db.execute(
                select(BBGame.id)
                .where(
                    (BBGame.home_team_id == team_id) | (BBGame.away_team_id == team_id),
                    BBGame.status == "post",
                    BBGame.season_type == 2,
                )
                .order_by(BBGame.tipoff_at.desc())
                .limit(settings.bb_rate_window)
            )
        ).scalars()
    ]
    if not game_ids:
        return []
    rows = (
        await db.execute(
            select(
                BBPlayerGameStat.athlete_id,
                BBPlayerGameStat.athlete_name,
                BBPlayerGameStat.points,
                BBPlayerGameStat.blocks,
            ).where(
                BBPlayerGameStat.team_id == team_id,
                BBPlayerGameStat.game_id.in_(game_ids),
            )
        )
    ).all()
    return [(str(a), str(n), int(p), int(b)) for a, n, p, b in rows]


async def _lineup_state(
    db: AsyncSession, game: BBGame, parsed: ParsedSummary
) -> tuple[bool, str]:
    """Top-4 usage players + rim protector confirmed clear of injury flags."""
    if parsed.injuries is None:
        return False, "injury report unavailable"
    required: dict[str, str] = {}
    for team_id, team_name in ((game.home_team_id, game.home_team), (game.away_team_id, game.away_team)):
        players = aggregate_players(await _team_player_rows(db, team_id))
        top4, rim = top_usage_and_rim(players, settings.bb_min_player_games)
        if len(top4) < 4:
            return False, f"{team_name}: usage data insufficient ({len(top4)}/4 players)"
        if rim is None:
            return False, f"{team_name}: rim-protector data insufficient"
        for player in list(top4) + [rim]:
            required[player.athlete_id] = f"{player.name} ({team_name})"

    flagged: list[str] = []
    for athlete_id, label in required.items():
        report = parsed.injuries.get(athlete_id)
        if report is None:
            continue
        status = report.get("status", "")
        if status in CLEAR_STATUSES:
            continue
        short = status.replace("INJURY_STATUS_", "").lower() or (report.get("fantasy") or "flagged").lower()
        flagged.append(f"{label} {short}")
    if flagged:
        return False, "; ".join(flagged)
    return True, f"{len(required)} key players clear"


def _tanking_teams(parsed: ParsedSummary, teams: list[tuple[str, str]]) -> tuple[bool, list[str]]:
    if parsed.standings is None:
        return False, []
    risk: list[str] = []
    for team_id, team_name in teams:
        record = parsed.standings.get(team_id)
        if record is None:
            return False, []  # standings present but incomplete -> unknown, gate fails
        wins, losses = record
        games = wins + losses
        if games <= 0:
            continue
        win_pct = wins / games
        if games >= settings.bb_tanking_min_games and win_pct <= settings.bb_tanking_win_pct_max:
            risk.append(f"{team_name} ({wins}-{losses})")
    return True, risk


async def build_context(db: AsyncSession, game: BBGame, parsed: ParsedSummary) -> GameContext:
    """Assemble every gate input for one game from stored history + live summary."""
    ctx = GameContext(home_name=game.home_team, away_name=game.away_team)

    home_games = await _finished_team_games(db, game.home_team_id)
    away_games = await _finished_team_games(db, game.away_team_id)
    settings_window = settings.bb_rate_window

    ctx.home_rate, ctx.home_samples = over_rate(home_games, settings_window)
    ctx.away_rate, ctx.away_samples = over_rate(away_games, settings_window)
    ctx.away_last10_rate, ctx.away_last10_samples = over_rate(away_games, 10)

    h2h = await _h2h_games(db, game.home_team_id, game.away_team_id)
    ctx.h2h_pace, ctx.h2h_meetings = h2h_pace(
        h2h,
        game.home_team_id,
        game.away_team_id,
        window=settings.bb_h2h_window,
        league_ppp=settings.bb_league_ppp,
    )

    ctx.lineup_confirmed, ctx.lineup_reason = await _lineup_state(db, game, parsed)

    last_home = await _last_finished(db, game.home_team_id, game.tipoff_at)
    last_away = await _last_finished(db, game.away_team_id, game.tipoff_at)
    ctx.home_b2b = back_to_back(
        [FinishedGame(tipoff=last_home.tipoff_at, home_team_id=last_home.home_team_id,
                      away_team_id=last_home.away_team_id, home_score=0, away_score=0, line=None)]
        if last_home else [],
        game.tipoff_at,
    )
    ctx.away_b2b = back_to_back(
        [FinishedGame(tipoff=last_away.tipoff_at, home_team_id=last_away.home_team_id,
                      away_team_id=last_away.away_team_id, home_score=0, away_score=0, line=None)]
        if last_away else [],
        game.tipoff_at,
    )

    standings_ok, risk = _tanking_teams(
        parsed, [(game.home_team_id, game.home_team), (game.away_team_id, game.away_team)]
    )
    ctx.standings_available = standings_ok
    ctx.tanking_teams = tuple(risk)

    ctx.market_total = parsed.total
    ctx.fair_implied_over = model.fair_implied_over(parsed.over_odds, parsed.under_odds)

    snapshots = (
        await db.execute(
            select(BBLineSnapshot.over_under, BBLineSnapshot.captured_at)
            .where(BBLineSnapshot.game_id == game.id)
            .order_by(BBLineSnapshot.captured_at.asc())
        )
    ).all()
    if snapshots:
        ctx.first_line = float(snapshots[0][0])
        ctx.current_line = float(snapshots[-1][0])

    # Expected totals from home/away venue splits (strict: min samples or None).
    home_splits = [g for g in home_games if _is_home(g, game.home_team_id)]
    away_splits = [g for g in away_games if _is_away(g, game.away_team_id)]
    needed = settings.bb_min_rate_samples
    if len(home_splits) >= needed and len(away_splits) >= needed:
        home_ppg = sum(g.home_score for g in home_splits) / len(home_splits)
        home_apg = sum(g.away_score for g in home_splits) / len(home_splits)
        away_ppg = sum(g.away_score for g in away_splits) / len(away_splits)
        away_apg = sum(g.home_score for g in away_splits) / len(away_splits)
        ctx.model_total = model.predicted_total(
            home_ppg,
            home_apg,
            away_ppg,
            away_apg,
            home_advantage=settings.bb_home_advantage,
        )
        if parsed.total is not None:
            ctx.p_over = model.p_over(ctx.model_total, parsed.total, settings.bb_total_sd)
        else:
            ctx.p_over = None
    else:
        ctx.model_total = None
        ctx.p_over = None

    return ctx


def _is_home(g: FinishedGame, team_id: str) -> bool:
    return g.home_team_id == team_id


def _is_away(g: FinishedGame, team_id: str) -> bool:
    return g.away_team_id == team_id


async def ensure_history(
    db: AsyncSession, client: ESPNClient, game: BBGame, budget: list[int]
) -> int:
    """Keep schedules fresh and pull summaries for recent games missing data."""
    fetched = 0
    now = datetime.now(timezone.utc).timestamp()
    for team_id in (game.home_team_id, game.away_team_id):
        for season in season_years():
            key = (team_id, season)
            if now - _schedule_seen.get(key, 0.0) < _SCHEDULE_REFRESH_SECONDS:
                continue
            _schedule_seen[key] = now
            try:
                await ingest_team_schedule(db, client, team_id, season)
            except ESPNError as exc:
                logger.warning("schedule ingest failed for team %s season %s: %s", team_id, season, exc)

    if budget[0] <= 0:
        return fetched

    from sqlalchemy import exists as sa_exists  # local import keeps top tidy

    line_missing = ~sa_exists(
        select(BBLineSnapshot.id).where(BBLineSnapshot.game_id == BBGame.id).correlate(BBGame)
    )
    players_missing = ~sa_exists(
        select(BBPlayerGameStat.id).where(BBPlayerGameStat.game_id == BBGame.id).correlate(BBGame)
    )
    missing = (
        await db.execute(
            select(BBGame.id)
            .where(
                (BBGame.home_team_id == game.home_team_id)
                | (BBGame.away_team_id == game.away_team_id),
                BBGame.season_type == 2,
                BBGame.status == "post",
                BBGame.tipoff_at < now_aware(),
                line_missing | players_missing,
            )
            .order_by(BBGame.tipoff_at.desc())
            .limit(budget[0])
        )
    ).scalars().all()

    for game_id in missing:
        if budget[0] <= 0:
            break
        row = await db.get(BBGame, game_id)
        if row is None:
            continue
        try:
            await ingest_summary(db, client, row)
            budget[0] -= 1
            fetched += 1
        except ESPNError as exc:
            logger.warning("summary ingest failed for %s: %s", game_id, exc)
            budget[0] -= 1
    return fetched


def now_aware() -> datetime:
    return datetime.now(timezone.utc)


async def _save_gate_run(
    db: AsyncSession, game: BBGame, report: AbsoluteFilterReport, ctx: GameContext
) -> BBGateRun:
    run = BBGateRun(
        game_id=game.id,
        passed=report.passed,
        checks=report.as_checks(),
        model_total=ctx.model_total,
        p_over=ctx.p_over,
        edge=(ctx.p_over - ctx.fair_implied_over)
        if ctx.p_over is not None and ctx.fair_implied_over is not None
        else None,
        market_total=ctx.market_total,
    )
    db.add(run)
    await db.flush()
    return run


async def _sync_tip(
    db: AsyncSession, game: BBGame, report: AbsoluteFilterReport, ctx: GameContext, run: BBGateRun
) -> str:
    """Upsert a PENDING tip when everything passes, reject otherwise."""
    if ctx.market_total is None or ctx.model_total is None or ctx.p_over is None:
        return "no-tip"
    edge = (ctx.p_over - ctx.fair_implied_over) if ctx.fair_implied_over is not None else None
    if edge is None:
        return "no-tip"

    tip = (
        await db.execute(select(BBTip).where(BBTip.game_id == game.id))
    ).scalar_one_or_none()
    if report.passed:
        if tip is None:
            tip = BBTip(
                game_id=game.id,
                status="PENDING",
                pick="OVER",
                line=float(ctx.market_total),
                over_odds=None,
                model_total=float(ctx.model_total),
                p_over=float(ctx.p_over),
                edge=float(edge),
                gate_run_id=run.id,
            )
            db.add(tip)
            return "tipped"
        if tip.status in ("PENDING", "AUTOMATED_REJECTED"):
            tip.status = "PENDING"
            tip.line = float(ctx.market_total)
            tip.model_total = float(ctx.model_total)
            tip.p_over = float(ctx.p_over)
            tip.edge = float(edge)
            tip.gate_run_id = run.id
            tip.notes = None
            tip.settled_at = None
            return "tipped"
        return "no-tip"

    if tip is not None and tip.status == "PENDING":
        first_failure = report.failures[0] if report.failures else None
        tip.status = "AUTOMATED_REJECTED"
        tip.gate_run_id = run.id
        tip.settled_at = datetime.now(timezone.utc)
        tip.notes = (
            f"rejected: {first_failure.gate} - {first_failure.reason}" if first_failure else "rejected"
        )
        return "rejected"
    return "no-tip"


async def settle_tips(db: AsyncSession) -> int:
    """Resolve pending tips once their game is final."""
    rows = (
        await db.execute(
            select(BBTip, BBGame)
            .join(BBGame, BBGame.id == BBTip.game_id)
            .where(
                BBTip.status == "PENDING",
                BBGame.status == "post",
                BBGame.home_score.is_not(None),
                BBGame.away_score.is_not(None),
            )
        )
    ).all()
    settled = 0
    for tip, game in rows:
        total = int(game.home_score or 0) + int(game.away_score or 0)
        if total == tip.line:
            tip.status = "PUSH"
        elif total > tip.line:
            tip.status = "WON"
        else:
            tip.status = "LOST"
        tip.settled_at = datetime.now(timezone.utc)
        settled += 1
    if settled:
        await db.commit()
    return settled


async def run_scan(db: AsyncSession, *, manual: bool = False) -> dict:
    """Evaluate today's slate through the ten-gate filter."""
    stats = {
        "slate": 0,
        "evaluated": 0,
        "passed": 0,
        "locked": 0,
        "rejected": 0,
        "settled": 0,
        "history_fetched": 0,
        "live": 0,
        "skipped": 0,
        "errors": 0,
        "manual": manual,
    }
    if not settings.bb_enabled:
        return stats

    now = datetime.now(timezone.utc)
    today_et = now.astimezone(ET).date()
    budget = [settings.bb_max_history_fetch_per_scan]
    thresholds = Thresholds.from_settings(settings)

    async with ESPNClient() as client:
        events: list[dict] = []
        # Yesterday (for late finals) through the lookahead horizon, so upcoming
        # games are evaluated ahead of their day too. Gate inputs that only exist
        # near tip-off (market line, lineups) simply fail until they arrive.
        for offset in range(-1, settings.bb_lookahead_days + 1):
            day = today_et + timedelta(days=offset)
            try:
                events.extend(await client.scoreboard(day))
            except ESPNError as exc:
                logger.warning("scoreboard fetch failed for %s: %s", day, exc)
                stats["errors"] += 1

        games = await ingest_events(db, events)
        stats["slate"] = len(games)
        stats["live"] = sum(1 for g in games if g.status == "live")

        for game in sorted(games, key=lambda g: g.tipoff_at):
            event_id = str(game.espn_event_id)
            if game.status == "post":
                # Keep lines/box scores fresh for finished slate games, then settle.
                try:
                    await ingest_summary(db, client, game)
                except ESPNError as exc:
                    await db.rollback()
                    stats["errors"] += 1
                    logger.warning("summary ingest failed for %s: %s", event_id, exc)
                stats["settled"] += await settle_tips(db)
                continue
            locked = now >= game.tipoff_at - timedelta(minutes=settings.bb_lock_minutes)
            # Far-future games change slowly: refresh them at most every
            # bb_lookahead_refresh_minutes instead of on every tick. Games within
            # that window of tip-off (and everything today) always run.
            quiet_until = now + timedelta(minutes=settings.bb_lookahead_refresh_minutes)
            if game.tipoff_at > quiet_until:
                last_run_at = (
                    await db.execute(
                        select(BBGateRun.ran_at)
                        .where(BBGateRun.game_id == game.id)
                        .order_by(BBGateRun.ran_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if last_run_at is not None:
                    if last_run_at.tzinfo is None:
                        last_run_at = last_run_at.replace(tzinfo=timezone.utc)
                    if now - last_run_at < timedelta(minutes=settings.bb_lookahead_refresh_minutes):
                        stats["skipped"] += 1
                        continue
            try:
                parsed = await ingest_summary(db, client, game)
                if locked:
                    stats["locked"] += 1
                    continue
                stats["history_fetched"] += await ensure_history(db, client, game, budget)
                ctx = await build_context(db, game, parsed)
                report = evaluate(ctx, thresholds)
                run = await _save_gate_run(db, game, report, ctx)
                outcome = await _sync_tip(db, game, report, ctx, run)
                await db.commit()
                stats["evaluated"] += 1
                if report.passed:
                    stats["passed"] += 1
                elif outcome == "rejected":
                    stats["rejected"] += 1
            except ESPNError as exc:
                await db.rollback()
                stats["errors"] += 1
                logger.warning("scan failed for event %s: %s", event_id, exc)
            except Exception:
                await db.rollback()
                stats["errors"] += 1
                logger.exception("unexpected scan failure for %s", event_id)

        # Settlement for games that finished outside this loop (e.g. late finals).
        stats["settled"] += await settle_tips(db)

    LAST_SCAN["at"] = datetime.now(timezone.utc).isoformat()
    LAST_SCAN["stats"] = stats
    return stats


async def backfill(
    db: AsyncSession, seasons: list[int], max_games: int, job: dict
) -> dict:
    """Pull schedules for all 30 teams, then summaries for finished games."""
    job.update({"state": "running", "teams_done": 0, "fetched": 0, "errors": 0, "started_at": datetime.now(timezone.utc).isoformat()})
    try:
        async with ESPNClient() as client:
            teams = await client.teams()
            for team in teams:
                team_id = str((team.get("team") or team).get("id") or "")
                if not team_id:
                    raw = team.get("team") or team
                    team_id = str(raw.get("id") or "")
                if not team_id:
                    continue
                for season in seasons:
                    try:
                        await ingest_team_schedule(db, client, team_id, season)
                    except ESPNError as exc:
                        job["errors"] = int(job["errors"]) + 1
                        logger.warning("backfill schedule failed (%s, %s): %s", team_id, season, exc)
                job["teams_done"] = int(job["teams_done"]) + 1

            from sqlalchemy import exists as sa_exists

            line_missing = ~sa_exists(
                select(BBLineSnapshot.id).where(BBLineSnapshot.game_id == BBGame.id).correlate(BBGame)
            )
            players_missing = ~sa_exists(
                select(BBPlayerGameStat.id).where(BBPlayerGameStat.game_id == BBGame.id).correlate(BBGame)
            )
            missing = (
                await db.execute(
                    select(BBGame.id)
                    .where(
                        BBGame.season_type == 2,
                        BBGame.status == "post",
                        BBGame.home_score.is_not(None),
                        line_missing | players_missing,
                    )
                    .order_by(BBGame.tipoff_at.desc())
                    .limit(max_games)
                )
            ).scalars().all()

            for game_id in missing:
                row = await db.get(BBGame, game_id)
                if row is None:
                    continue
                try:
                    await ingest_summary(db, client, row)
                    job["fetched"] = int(job["fetched"]) + 1
                    job["last_event"] = row.espn_event_id
                except ESPNError as exc:
                    job["errors"] = int(job["errors"]) + 1
                    logger.warning("backfill summary failed for %s: %s", game_id, exc)
    except Exception as exc:  # noqa: BLE001 - job must record any failure
        job["state"] = "failed"
        job["error"] = str(exc)
        logger.exception("backfill failed")
        return job
    job["state"] = "done"
    job["finished_at"] = datetime.now(timezone.utc).isoformat()
    return job


async def audit(db: AsyncSession, window_days: int) -> dict:
    """Measured hit rate: settled tips + the model's paper OVER verdicts on finished evaluated games."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    # Real (informational) tips inside the window.
    tip_rows = (
        await db.execute(
            select(BBTip, BBGame)
            .join(BBGame, BBGame.id == BBTip.game_id)
            .where(BBTip.created_at >= cutoff)
        )
    ).all()
    counts = {"WON": 0, "LOST": 0, "PUSH": 0, "PENDING": 0, "AUTOMATED_REJECTED": 0}
    for tip, _game in tip_rows:
        counts[tip.status] = counts.get(tip.status, 0) + 1

    # Paper verdicts -- every finished game we evaluated where the model leaned
    # OVER confidently (g10 rule: model_total > market and p_over >= 60%). The
    # verdict is compared against the closing market line so the measured hit
    # rate stays live even while real tips remain informational (never placed).
    paper = {"won": 0, "lost": 0, "push": 0}
    clv_points_list: list[float] = []
    finished = (
        await db.execute(
            select(BBGame).where(
                BBGame.status == "post",
                BBGame.home_score.is_not(None),
                BBGame.away_score.is_not(None),
                BBGame.tipoff_at >= cutoff,
            )
        )
    ).scalars().all()
    if finished:
        game_ids = [g.id for g in finished]
        game_by_id = {g.id: g for g in finished}
        runs = (
            await db.execute(
                select(BBGateRun)
                .where(BBGateRun.game_id.in_(game_ids))
                .order_by(BBGateRun.ran_at.desc())
            )
        ).scalars().all()
        snaps = (
            await db.execute(
                select(BBLineSnapshot)
                .where(BBLineSnapshot.game_id.in_(game_ids))
                .order_by(BBLineSnapshot.captured_at.desc())
            )
        ).scalars().all()
        latest_run: dict[object, BBGateRun] = {}
        for r in runs:
            latest_run.setdefault(r.game_id, r)
        latest_line: dict[object, float] = {}
        closing: dict[object, float] = {}
        for s in snaps:
            latest_line.setdefault(s.game_id, s.over_under)
            g = game_by_id.get(s.game_id)
            if g is not None and s.captured_at <= g.tipoff_at:
                closing.setdefault(s.game_id, s.over_under)
        for g in finished:
            run = latest_run.get(g.id)
            line = latest_line.get(g.id)
            if run is None or line is None or run.model_total is None or run.p_over is None:
                continue
            if not (run.model_total > line and run.p_over >= 0.60):
                continue  # the model never committed to OVER for this game
            total = (g.home_score or 0) + (g.away_score or 0)
            if total > line:
                paper["won"] += 1
            elif total < line:
                paper["lost"] += 1
            else:
                paper["push"] += 1
            # CLV: did the decision-time line beat the closing line?
            if run.market_total is not None and g.id in closing:
                clv_points_list.append(closing[g.id] - run.market_total)

    won = counts["WON"] + paper["won"]
    lost = counts["LOST"] + paper["lost"]
    push = counts["PUSH"] + paper["push"]
    decided = won + lost
    clv_n = len(clv_points_list)
    return {
        "window_days": window_days,
        "tips": len(tip_rows),
        "won": won,
        "lost": lost,
        "push": push,
        "pending": counts["PENDING"],
        "rejected": counts["AUTOMATED_REJECTED"],
        "hit_rate": (won / decided) if decided else None,
        "paper": paper,
        "clv": {
            "n": clv_n,
            "avg_points": (sum(clv_points_list) / clv_n) if clv_n else None,
            "beat_close_pct": (sum(1 for x in clv_points_list if x > 0) / clv_n) if clv_n else None,
        },
    }


async def shadow_backtest(db: AsyncSession) -> dict:
    """Read-only what-if replay of the model over every finished game.

    Scores candidate selection rules (model edge, line caps, season over-rate
    floors) on history instead of the few games that have stored gate runs.
    Never writes rows and never changes live filter behaviour.
    """
    games = (
        await db.execute(
            select(BBGame).where(
                BBGame.status == "post",
                BBGame.home_score.is_not(None),
                BBGame.away_score.is_not(None),
            )
        )
    ).scalars().all()
    ids = [g.id for g in games]
    latest: dict[object, BBLineSnapshot] = {}
    if ids:
        snaps = (
            await db.execute(
                select(BBLineSnapshot)
                .where(BBLineSnapshot.game_id.in_(ids))
                .order_by(BBLineSnapshot.captured_at.desc())
            )
        ).scalars().all()
        for s in snaps:
            latest.setdefault(s.game_id, s)

    hist = [
        backtest.HistGame(
            tipoff=g.tipoff_at,
            season_type=g.season_type,
            home_team_id=g.home_team_id,
            away_team_id=g.away_team_id,
            home_score=int(g.home_score or 0),
            away_score=int(g.away_score or 0),
            line=(latest[g.id].over_under if g.id in latest else None),
            over_odds=(latest[g.id].over_odds if g.id in latest else None),
            under_odds=(latest[g.id].under_odds if g.id in latest else None),
        )
        for g in games
    ]
    rows = backtest.replay(
        hist,
        rate_window=settings.bb_rate_window,
        min_samples=settings.bb_min_rate_samples,
        home_advantage=settings.bb_home_advantage,
        sd=settings.bb_total_sd,
    )
    over = [r for r in rows if backtest.over_bet(r)]
    shadow_games = [
        shadow.ShadowGame(
            passed=False,  # gates 5/7/9 cannot be rebuilt from history
            model_total=r.model_total,
            p_over=r.p_over,
            edge=r.edge,
            line=r.line,
            close=r.line,
            over_odds=r.over_decimal,
            under_odds=r.under_decimal,
            total=r.total,
        )
        for r in rows
    ]
    window = None
    if rows:
        window = {
            "start": min(r.tipoff for r in rows).date().isoformat(),
            "end": max(r.tipoff for r in rows).date().isoformat(),
        }
    return {
        "games_with_scores": len(games),
        "games_with_line": sum(1 for h in hist if h.line is not None),
        "model_rows": len(rows),
        "window": window,
        "baseline_model_over": backtest.summarize(over),
        "edge_sweep": backtest.edge_sweep(
            rows,
            edge_minima=(0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30),
            line_caps=(None, 235.0, 230.0, 225.0, 220.0, 215.0),
        ),
        "rate_sweep": backtest.rate_sweep(
            rows,
            home_away_minima=(0.48, 0.55, 0.60, 0.65, 0.68),
            last10_minima=(0.50, 0.60, 0.65, 0.70),
        ),
        "line_buckets": backtest.line_buckets(
            rows, (0.0, 215.0, 220.0, 225.0, 230.0, 235.0, 240.0, 245.0, 260.0, 400.0)
        ),
        "candidate_rules": shadow.score(shadow_games),
        "note": "read-only shadow backtest; live filter and tips unchanged",
    }


async def shadow_record(db: AsyncSession) -> dict:
    """Live paper record for candidate rules over finished evaluated games.

    Only games whose latest gate run stored the decision-time line
    (``market_total``) are included, so every entry is a genuine pre-tip
    decision rather than a hindsight line. Read-only: the official audit and
    the informational tips are never touched.
    """
    games = (
        await db.execute(
            select(BBGame).where(
                BBGame.status == "post",
                BBGame.home_score.is_not(None),
                BBGame.away_score.is_not(None),
            )
        )
    ).scalars().all()
    shadow_games: list[shadow.ShadowGame] = []
    if games:
        ids = [g.id for g in games]
        runs = (
            await db.execute(
                select(BBGateRun)
                .where(BBGateRun.game_id.in_(ids))
                .order_by(BBGateRun.ran_at.desc())
            )
        ).scalars().all()
        snaps = (
            await db.execute(
                select(BBLineSnapshot)
                .where(BBLineSnapshot.game_id.in_(ids))
                .order_by(BBLineSnapshot.captured_at.desc())
            )
        ).scalars().all()
        latest_run: dict[object, BBGateRun] = {}
        for r in runs:
            latest_run.setdefault(r.game_id, r)
        game_by_id = {g.id: g for g in games}
        closing: dict[object, BBLineSnapshot] = {}
        for s in snaps:
            g = game_by_id.get(s.game_id)
            if g is not None and s.captured_at <= g.tipoff_at:
                closing.setdefault(s.game_id, s)
        for g in games:
            run = latest_run.get(g.id)
            if run is None or run.model_total is None or run.market_total is None:
                continue
            close_snap = closing.get(g.id)
            shadow_games.append(
                shadow.ShadowGame(
                    passed=run.passed,
                    model_total=run.model_total,
                    p_over=run.p_over,
                    edge=run.edge,
                    line=run.market_total,
                    close=(close_snap.over_under if close_snap else None),
                    over_odds=model.normalize_odds(close_snap.over_odds) if close_snap else None,
                    under_odds=model.normalize_odds(close_snap.under_odds) if close_snap else None,
                    total=(g.home_score or 0) + (g.away_score or 0),
                )
            )
    return {
        "games": len(shadow_games),
        "rules": shadow.score(shadow_games),
        "note": "shadow paper record; fills as gate runs record decision-time lines",
    }

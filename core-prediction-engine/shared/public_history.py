"""Public results for placed trebles. Stake is 2,000 on each match and each treble."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from shared.corner_results import corner_leg_outcome
from shared.poisson import leg_won_over_15
from shared.time_buckets import local_day

STAKE = 2000


@dataclass
class HistoryLeg:
    fixture_id: str
    home_team: str
    away_team: str
    kickoff_at: datetime
    odds: float
    home_goals: int | None
    away_goals: int | None
    finished: bool
    practice: bool
    market: str = "Over 1.5 Goals"
    fh_corners: int | None = None
    fh_half_complete: bool = False


@dataclass
class HistorySlip:
    slip_id: str
    placed_at: datetime
    legs: list[HistoryLeg]
    forced: bool = False


def leg_result(leg: HistoryLeg) -> str:
    if "Corner" in leg.market:
        half_done = leg.fh_half_complete or (leg.finished and leg.fh_corners is not None)
        return corner_leg_outcome(leg.market, leg.fh_corners, half_done)
    if leg.home_goals is None or leg.away_goals is None:
        return "pending"
    if leg_won_over_15(leg.home_goals, leg.away_goals):
        return "won"
    if leg.finished:
        return "lost"
    return "pending"


def single_profit(odds: float, result: str) -> float | None:
    if result == "won":
        return round((odds - 1.0) * STAKE, 2)
    if result == "lost":
        return float(-STAKE)
    return None


def treble_profit(legs: list[HistoryLeg]) -> float | None:
    results = [leg_result(leg) for leg in legs]
    if not results:
        return None
    if any(result == "lost" for result in results):
        return float(-STAKE)
    if any(result == "pending" for result in results):
        return None
    product = 1.0
    for leg in legs:
        product *= leg.odds
    return round((product - 1.0) * STAKE, 2)


def _nairobi_date(moment: datetime) -> str:
    return local_day(moment).isoformat()


def build_public_history(slips: list[HistorySlip]) -> dict:
    unique: dict[str, HistoryLeg] = {}
    for slip in sorted(slips, key=lambda item: item.placed_at):
        for leg in slip.legs:
            unique.setdefault(f"{leg.fixture_id}:{leg.market}", leg)

    matches_won = matches_lost = matches_pending = 0
    days: dict[str, dict] = defaultdict(
        lambda: {
            "matches_won": 0,
            "matches_lost": 0,
            "single_profit": 0.0,
            "trebles_placed": 0,
            "trebles_won": 0,
            "trebles_lost": 0,
            "trebles_pending": 0,
            "treble_profit": 0.0,
        }
    )

    for leg in unique.values():
        result = leg_result(leg)
        day = _nairobi_date(leg.kickoff_at)
        if result == "won":
            matches_won += 1
            days[day]["matches_won"] += 1
        elif result == "lost":
            matches_lost += 1
            days[day]["matches_lost"] += 1
        else:
            matches_pending += 1
        profit = single_profit(leg.odds, result)
        if profit is not None:
            days[day]["single_profit"] = round(days[day]["single_profit"] + profit, 2)

    trebles_won = trebles_lost = trebles_pending = 0
    history = []
    for slip in _unique_accumulators(slips):
        profit = treble_profit(slip.legs)
        slip_days = sorted({_nairobi_date(leg.kickoff_at) for leg in slip.legs})
        day = slip_days[0]
        date_label = "|".join(slip_days)
        days[day]["trebles_placed"] += 1
        if profit is None:
            trebles_pending += 1
            days[day]["trebles_pending"] += 1
            slip_result = "pending"
        elif profit < 0:
            trebles_lost += 1
            days[day]["trebles_lost"] += 1
            days[day]["treble_profit"] = round(days[day]["treble_profit"] + profit, 2)
            slip_result = "lost"
        else:
            trebles_won += 1
            days[day]["trebles_won"] += 1
            days[day]["treble_profit"] = round(days[day]["treble_profit"] + profit, 2)
            slip_result = "won"
        history.append(
            {
                "slip_id": slip.slip_id,
                "date": date_label,
                "forced": slip.forced,
                "result": slip_result,
                "combined_odds": round(_product(slip.legs), 2),
                "profit": profit,
                "legs": [
                    {
                        "home_team": leg.home_team,
                        "away_team": leg.away_team,
                        "odds": leg.odds,
                        "result": leg_result(leg),
                        "market": leg.market,
                        "home_goals": leg.home_goals,
                        "away_goals": leg.away_goals,
                        "fh_corners": leg.fh_corners,
                        "practice": leg.practice,
                    }
                    for leg in slip.legs
                ],
            }
        )

    history.sort(key=lambda row: row["date"], reverse=True)
    day_rows = []
    for date in sorted(days, reverse=True):
        row = days[date]
        day_rows.append(
            {
                "date": date,
                "matches_won": row["matches_won"],
                "matches_lost": row["matches_lost"],
                "single_profit": round(row["single_profit"], 2),
                "trebles_placed": row["trebles_placed"],
                "trebles_won": row["trebles_won"],
                "trebles_lost": row["trebles_lost"],
                "trebles_pending": row["trebles_pending"],
                "treble_profit": round(row["treble_profit"], 2),
            }
        )

    single_total = round(sum(row["single_profit"] for row in day_rows), 2)
    treble_total = round(sum(row["treble_profit"] for row in day_rows), 2)
    return {
        "stake": STAKE,
        "matches_won": matches_won,
        "matches_lost": matches_lost,
        "matches_pending": matches_pending,
        "trebles_placed": trebles_won + trebles_lost + trebles_pending,
        "trebles_won": trebles_won,
        "trebles_lost": trebles_lost,
        "trebles_pending": trebles_pending,
        "single_profit": single_total,
        "treble_profit": treble_total,
        "days": day_rows,
        "slips": history[:40],
    }


def _unique_accumulators(slips: list[HistorySlip]) -> list[HistorySlip]:
    """One row when every account placed the same three matches."""
    seen: dict[tuple[str, ...], HistorySlip] = {}
    for slip in sorted(slips, key=lambda item: item.placed_at):
        if len(slip.legs) != 3:
            continue
        key = tuple(sorted(leg.fixture_id for leg in slip.legs))
        kept = seen.get(key)
        if kept is None:
            seen[key] = slip
        elif slip.forced:
            kept.forced = True
    return list(seen.values())


def _product(legs: list[HistoryLeg]) -> float:
    product = 1.0
    for leg in legs:
        product *= leg.odds
    return product

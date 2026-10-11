"""Home and away scoring rates from finished matches, weighted toward recent games."""

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from shared.league_names import league_key
from shared.team_names import team_key
from shared.time_buckets import local_day

HALF_LIFE_DAYS = 21
MIN_VENUE_GAMES = 6
MIN_LEAGUE_GAMES = 20
NAIROBI = ZoneInfo("Africa/Nairobi")

# What every odds feed writes onto a fixture it has no history for. It is a
# placeholder, never an estimate, so a fixture still holding it must not be priced.
PLACEHOLDER_LAMBDA_HOME = 1.4
PLACEHOLDER_LAMBDA_AWAY = 1.1


def _weight(played_on: date, today: date) -> float:
    age = max((today - played_on).days, 0)
    return 0.5 ** (age / HALF_LIFE_DAYS)


def _avg(samples: list[tuple[float, float]]) -> float | None:
    total_weight = sum(weight for weight, _ in samples)
    if total_weight <= 0:
        return None
    return sum(weight * value for weight, value in samples) / total_weight


@dataclass(frozen=True, slots=True)
class HistoryMatch:
    """A finished match reduced to plain values.

    The scoring walk reads every field of every candidate match for every
    upcoming fixture, which is millions of reads. On a SQLAlchemy object each
    read goes through the ORM instrumentation; on this it is a plain slot. The
    keys and the local day are computed once here instead of per pair.
    """

    home_key: str
    away_key: str
    league_key: str | None
    league: str
    day: date
    day_iso: str
    home_goals: int
    away_goals: int


def project_history(matches) -> list[HistoryMatch]:
    """Reduce finished matches to plain rows, dropping any without a score."""
    rows: list[HistoryMatch] = []
    for match in matches:
        if match.home_goals is None or match.away_goals is None:
            continue
        day = local_day(match.kickoff_at)
        rows.append(
            HistoryMatch(
                home_key=team_key(match.home_team),
                away_key=team_key(match.away_team),
                league_key=league_key(match.league),
                league=match.league,
                day=day,
                day_iso=day.isoformat(),
                home_goals=match.home_goals,
                away_goals=match.away_goals,
            )
        )
    return rows


class HistoryIndex:
    """Finished matches grouped so a fixture only walks its own competition.

    Without this, every upcoming fixture rescanned the whole history; with it,
    a fixture sees only the matches whose league could possibly qualify.
    """

    def __init__(self, rows: list[HistoryMatch]) -> None:
        self.by_league_key: dict[str, list[HistoryMatch]] = {}
        self.by_league_label: dict[str, list[HistoryMatch]] = {}
        for row in rows:
            if row.league_key:
                self.by_league_key.setdefault(row.league_key, []).append(row)
            self.by_league_label.setdefault(row.league, []).append(row)

    def for_league(self, league: str) -> list[HistoryMatch]:
        wanted = league_key(league)
        if wanted:
            return self.by_league_key.get(wanted, [])
        return self.by_league_label.get(league, []) if league else []


def _estimate_from_rows(
    candidates: list[HistoryMatch],
    *,
    home_key: str,
    away_key: str,
    today: date,
) -> tuple[float, float] | None:
    """Attack and defence strengths from rows already known to be in-league."""
    finished: list[HistoryMatch] = []
    seen: set[tuple[str, str, str]] = set()
    for row in candidates:
        stamp = (row.home_key, row.away_key, row.day_iso)
        if stamp in seen:
            continue
        seen.add(stamp)
        finished.append(row)
    if len(finished) < MIN_LEAGUE_GAMES:
        return None

    finished.sort(key=lambda row: row.day, reverse=True)
    home_games = [row for row in finished if row.home_key == home_key][:12]
    away_games = [row for row in finished if row.away_key == away_key][:12]
    if len(home_games) < MIN_VENUE_GAMES or len(away_games) < MIN_VENUE_GAMES:
        return None

    league_home = _avg([(_weight(row.day, today), row.home_goals) for row in finished])
    league_away = _avg([(_weight(row.day, today), row.away_goals) for row in finished])
    if not league_home or not league_away:
        return None

    home_attack = _avg([(_weight(row.day, today), row.home_goals) for row in home_games])
    home_defence = _avg([(_weight(row.day, today), row.away_goals) for row in home_games])
    away_attack = _avg([(_weight(row.day, today), row.away_goals) for row in away_games])
    away_defence = _avg([(_weight(row.day, today), row.home_goals) for row in away_games])
    if None in (home_attack, home_defence, away_attack, away_defence):
        return None

    home_attack_strength = home_attack / league_home
    away_defence_strength = away_defence / league_away
    away_attack_strength = away_attack / league_away
    home_defence_strength = home_defence / league_home
    lambda_home = home_attack_strength * away_defence_strength * league_home
    lambda_away = away_attack_strength * home_defence_strength * league_away
    return round(min(max(lambda_home, 0.2), 4.0), 3), round(min(max(lambda_away, 0.2), 4.0), 3)


def estimate_match_lambdas(
    matches: list,
    *,
    home_team: str,
    away_team: str,
    league: str,
    today: date | None = None,
) -> tuple[float, float] | None:
    """λ home and λ away from attack and defence strengths. None when the sample is too thin.

    Projects `matches` on this call. Callers that score many fixtures at once
    should build a HistoryIndex once and use `estimate_from_index` instead.
    """
    today = today or datetime.now(NAIROBI).date()
    index = HistoryIndex(project_history(matches))
    return estimate_from_index(index, home_team=home_team, away_team=away_team, league=league, today=today)


def estimate_from_index(
    index: HistoryIndex,
    *,
    home_team: str,
    away_team: str,
    league: str,
    today: date,
) -> tuple[float, float] | None:
    """Same estimate, against a prebuilt index. One projection serves the whole run."""
    return _estimate_from_rows(
        index.for_league(league),
        home_key=team_key(home_team),
        away_key=team_key(away_team),
        today=today,
    )


def apply_form_lambdas(upcoming: list, history: list) -> set[UUID]:
    """Resolve scoring rates for this run and report which fixtures got a real one.

    A fixture whose sample is too thin keeps the import placeholder and falls out of
    the returned set, so the caller knows not to price it. Any estimate left over from
    an earlier run is cleared here: a value computed against history that has since
    been purged must not survive into a slip.
    """
    index = HistoryIndex(project_history(history))
    modeled: set[UUID] = set()
    for fixture in upcoming:
        if fixture.home_goals is not None:
            continue
        rates = estimate_from_index(
            index,
            home_team=fixture.home_team,
            away_team=fixture.away_team,
            league=fixture.league,
            today=local_day(fixture.kickoff_at),
        )
        if rates is None:
            if (
                fixture.lambda_home != PLACEHOLDER_LAMBDA_HOME
                or fixture.lambda_away != PLACEHOLDER_LAMBDA_AWAY
            ):
                fixture.lambda_home = PLACEHOLDER_LAMBDA_HOME
                fixture.lambda_away = PLACEHOLDER_LAMBDA_AWAY
            continue
        fixture.lambda_home, fixture.lambda_away = rates
        modeled.add(fixture.id)
    return modeled

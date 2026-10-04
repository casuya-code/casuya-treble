"""Home and away scoring rates from finished matches, weighted toward recent games."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from shared.time_buckets import local_day

HALF_LIFE_DAYS = 21
MIN_VENUE_GAMES = 6
MIN_LEAGUE_GAMES = 20
NAIROBI = ZoneInfo("Africa/Nairobi")


def _weight(played_on: date, today: date) -> float:
    age = max((today - played_on).days, 0)
    return 0.5 ** (age / HALF_LIFE_DAYS)


def _avg(samples: list[tuple[float, float]]) -> float | None:
    total_weight = sum(weight for weight, _ in samples)
    if total_weight <= 0:
        return None
    return sum(weight * value for weight, value in samples) / total_weight


def estimate_match_lambdas(
    matches: list,
    *,
    home_team: str,
    away_team: str,
    league: str,
    today: date | None = None,
) -> tuple[float, float] | None:
    """λ home and λ away from attack and defence strengths. None when the sample is too thin."""
    today = today or datetime.now(NAIROBI).date()
    finished = []
    for match in matches:
        if match.home_goals is None or match.away_goals is None:
            continue
        if league and match.league != league:
            continue
        finished.append(match)
    if len(finished) < MIN_LEAGUE_GAMES:
        return None

    finished.sort(key=lambda match: local_day(match.kickoff_at), reverse=True)
    home_games = [match for match in finished if match.home_team == home_team][:12]
    away_games = [match for match in finished if match.away_team == away_team][:12]
    if len(home_games) < MIN_VENUE_GAMES or len(away_games) < MIN_VENUE_GAMES:
        return None

    league_home = _avg([( _weight(local_day(match.kickoff_at), today), match.home_goals) for match in finished])
    league_away = _avg([( _weight(local_day(match.kickoff_at), today), match.away_goals) for match in finished])
    if not league_home or not league_away:
        return None

    home_attack = _avg(
        [(_weight(local_day(match.kickoff_at), today), match.home_goals) for match in home_games]
    )
    home_defence = _avg(
        [(_weight(local_day(match.kickoff_at), today), match.away_goals) for match in home_games]
    )
    away_attack = _avg(
        [(_weight(local_day(match.kickoff_at), today), match.away_goals) for match in away_games]
    )
    away_defence = _avg(
        [(_weight(local_day(match.kickoff_at), today), match.home_goals) for match in away_games]
    )
    if None in (home_attack, home_defence, away_attack, away_defence):
        return None

    home_attack_strength = home_attack / league_home
    away_defence_strength = away_defence / league_away
    away_attack_strength = away_attack / league_away
    home_defence_strength = home_defence / league_home
    lambda_home = home_attack_strength * away_defence_strength * league_home
    lambda_away = away_attack_strength * home_defence_strength * league_away
    return round(min(max(lambda_home, 0.2), 4.0), 3), round(min(max(lambda_away, 0.2), 4.0), 3)


def apply_form_lambdas(upcoming: list, history: list) -> int:
    """Replace stored scoring rates when a team has enough finished matches. Returns how many changed."""
    updated = 0
    for fixture in upcoming:
        if fixture.home_goals is not None:
            continue
        rates = estimate_match_lambdas(
            history,
            home_team=fixture.home_team,
            away_team=fixture.away_team,
            league=fixture.league,
            today=local_day(fixture.kickoff_at),
        )
        if rates is None:
            continue
        fixture.lambda_home, fixture.lambda_away = rates
        updated += 1
    return updated

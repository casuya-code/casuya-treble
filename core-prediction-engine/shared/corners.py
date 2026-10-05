"""First-half corner chances from recent corner counts, kept only when the price is generous."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from shared.league_names import league_key
from shared.poisson import edge_vs_market, implied_probability, poisson_pmf
from shared.team_names import team_key
from shared.team_strength import MIN_LEAGUE_GAMES, MIN_VENUE_GAMES, _avg, _weight
from shared.time_buckets import local_day
from shared.treble_generator import CandidateLeg, TrebleCandidate

# The score files record the full match. About 45% of corners arrive before half-time.
FIRST_HALF_SHARE = 0.45
MIN_CORNER_ODDS = 1.20
NAIROBI = ZoneInfo("Africa/Nairobi")
MARKET = {2.5: "Over 2.5 Corners 1H", 3.5: "Over 3.5 Corners 1H"}


def prob_over_line(lam: float, line: float) -> float:
    """Chance the corner count clears a .5 line. Over 2.5 means 3 or more."""
    need = int(line) + 1
    under = sum(poisson_pmf(k, lam) for k in range(need))
    return float(max(0.0, min(1.0, 1.0 - under)))


def estimate_first_half_corners(
    matches: list,
    *,
    home_team: str,
    away_team: str,
    league: str,
    today: date | None = None,
) -> float | None:
    """Expected first-half corners. None when the corner sample is too thin."""
    today = today or datetime.now(NAIROBI).date()
    wanted = league_key(league)
    home_key = team_key(home_team)
    away_key = team_key(away_team)
    finished = []
    seen: set[tuple[str, str, str]] = set()
    for match in matches:
        if match.home_corners is None or match.away_corners is None:
            continue
        if wanted:
            if league_key(match.league) != wanted:
                continue
        elif league and match.league != league:
            continue
        stamp = (team_key(match.home_team), team_key(match.away_team), local_day(match.kickoff_at).isoformat())
        if stamp in seen:
            continue
        seen.add(stamp)
        finished.append(match)
    if len(finished) < MIN_LEAGUE_GAMES:
        return None

    finished.sort(key=lambda match: local_day(match.kickoff_at), reverse=True)
    home_games = [match for match in finished if team_key(match.home_team) == home_key][:10]
    away_games = [match for match in finished if team_key(match.away_team) == away_key][:10]
    if len(home_games) < MIN_VENUE_GAMES or len(away_games) < MIN_VENUE_GAMES:
        return None

    def weighted(samples, value):
        return _avg([(_weight(local_day(match.kickoff_at), today), value(match)) for match in samples])

    league_home = weighted(finished, lambda match: match.home_corners)
    league_away = weighted(finished, lambda match: match.away_corners)
    home_attack = weighted(home_games, lambda match: match.home_corners)
    home_defence = weighted(home_games, lambda match: match.away_corners)
    away_attack = weighted(away_games, lambda match: match.away_corners)
    away_defence = weighted(away_games, lambda match: match.home_corners)
    if None in (league_home, league_away, home_attack, home_defence, away_attack, away_defence):
        return None
    if league_home <= 0 or league_away <= 0:
        return None

    lambda_home = (home_attack / league_home) * (away_defence / league_away) * league_home
    lambda_away = (away_attack / league_away) * (home_defence / league_home) * league_away
    total = min(max(lambda_home + lambda_away, 1.0), 16.0)
    return round(total * FIRST_HALF_SHARE, 3)


def _priced_lines(fixture) -> list[tuple[float, float]]:
    lines = []
    if fixture.fh_corner_over_25 and fixture.fh_corner_over_25 > 1.0:
        lines.append((2.5, float(fixture.fh_corner_over_25)))
    if fixture.fh_corner_over_35 and fixture.fh_corner_over_35 > 1.0:
        lines.append((3.5, float(fixture.fh_corner_over_35)))
    return lines


def corner_leg(fixture, history: list) -> CandidateLeg | None:
    """The 2.5 or 3.5 line where the model chance is higher than the price implies."""
    expected = estimate_first_half_corners(
        history,
        home_team=fixture.home_team,
        away_team=fixture.away_team,
        league=fixture.league,
        today=local_day(fixture.kickoff_at),
    )
    if expected is None:
        return None
    best: tuple[float, float, float, str] | None = None
    for line, odds in _priced_lines(fixture):
        if odds < MIN_CORNER_ODDS:
            continue
        probability = prob_over_line(expected, line)
        edge = edge_vs_market(probability, odds)
        if edge is None or edge <= 0 or probability <= implied_probability(odds):
            continue
        if best is None or edge > best[0]:
            best = (edge, odds, probability, MARKET[line])
    if best is None:
        return None
    _edge, odds, probability, market = best
    return CandidateLeg(
        fixture_id=fixture.id,
        odds=odds,
        model_probability=probability,
        kickoff_day=local_day(fixture.kickoff_at),
        market=market,
    )


def find_best_corner_trebles(
    fixtures: list,
    history: list,
    *,
    min_combined_odds: float = 3.0,
    limit: int = 5,
) -> list[TrebleCandidate]:
    legs = []
    for fixture in fixtures:
        leg = corner_leg(fixture, history)
        if leg is not None:
            legs.append(leg)
    # Reuse the same-day treble rules. The legs already cleared the corner price test.
    return _trebles_from_legs(legs, min_combined_odds=min_combined_odds, limit=limit)


def _trebles_from_legs(legs: list[CandidateLeg], *, min_combined_odds: float, limit: int) -> list[TrebleCandidate]:
    """Same pairing as the goals treble, for legs that are already eligible."""
    import itertools

    from shared.models import TimeCategory

    qualifying: list[TrebleCandidate] = []
    short: list[TrebleCandidate] = []
    for combo in itertools.combinations(legs, 3):
        days = {leg.kickoff_day for leg in combo}
        if len(days) != 1:
            continue
        combined_odds = combo[0].odds * combo[1].odds * combo[2].odds
        model_p = combo[0].model_probability * combo[1].model_probability * combo[2].model_probability
        candidate = TrebleCandidate(
            legs=combo,
            combined_odds=combined_odds,
            model_probability=model_p,
            time_category=TimeCategory.ALL_DAY,
            forced=combined_odds < min_combined_odds,
        )
        if candidate.forced:
            short.append(candidate)
        else:
            qualifying.append(candidate)
    if qualifying:
        qualifying.sort(key=lambda item: (item.model_probability, item.combined_odds), reverse=True)
        return qualifying[:limit]
    short.sort(key=lambda item: (item.combined_odds, item.model_probability), reverse=True)
    return short[:limit]

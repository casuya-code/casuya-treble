"""Distinguish practice/demo fixtures from real imported events."""

from datetime import datetime, timezone

DEMO_EXTERNAL_PREFIX = "demo-"


def is_demo_external_id(external_id: str | None) -> bool:
    if not external_id:
        return False
    return external_id.startswith(DEMO_EXTERNAL_PREFIX)


def is_demo_fixture(fixture) -> bool:
    return is_demo_external_id(getattr(fixture, "external_id", None))


def upcoming_fixtures(fixtures: list, now: datetime | None = None) -> list:
    """Drop matches that have already kicked off so trebles stay bettable."""
    moment = now or datetime.now(timezone.utc)
    upcoming = []
    for fixture in fixtures:
        kickoff = getattr(fixture, "kickoff_at", None)
        if kickoff is None:
            continue
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        if kickoff > moment:
            upcoming.append(fixture)
    return upcoming


def prefer_real_fixtures(fixtures: list) -> list:
    """Use real bookmaker fixtures when enough exist; otherwise allow demo for practice."""
    real = [f for f in fixtures if not is_demo_fixture(f)]
    if len(real) >= 3:
        return real
    return fixtures

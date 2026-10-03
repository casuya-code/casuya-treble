"""Homepage visitors. One browser counts once on each Nairobi day."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

NAIROBI = ZoneInfo("Africa/Nairobi")


def nairobi_today(moment: datetime | None = None) -> date:
    moment = moment or datetime.now(NAIROBI)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=ZoneInfo("UTC"))
    return moment.astimezone(NAIROBI).date()


def count_window_start(today: date) -> date:
    """Earliest day that can affect yesterday, this week, or this year."""
    yesterday = today - timedelta(days=1)
    week_start = today - timedelta(days=today.weekday())
    year_start = date(today.year, 1, 1)
    return min(yesterday, week_start, year_start)


def visit_totals(days_by_visitor: list[tuple[str, date]], today: date) -> dict[str, int]:
    """Unique visitors for today, yesterday, this week (Monday–today), and this year."""
    yesterday = today - timedelta(days=1)
    week_start = today - timedelta(days=today.weekday())
    year_start = date(today.year, 1, 1)

    def unique(start: date, end: date) -> int:
        return len({key for key, day in days_by_visitor if start <= day <= end})

    return {
        "today": unique(today, today),
        "yesterday": unique(yesterday, yesterday),
        "week": unique(week_start, today),
        "year": unique(year_start, today),
    }

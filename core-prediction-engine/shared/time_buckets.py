"""Nairobi calendar day. A treble uses matches from one date, midnight to midnight."""

from datetime import date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

DEFAULT_TZ = ZoneInfo("Africa/Nairobi")


@lru_cache(maxsize=None)
def local_kickoff(kickoff_at: datetime, tz: ZoneInfo = DEFAULT_TZ) -> datetime:
    if kickoff_at.tzinfo is None:
        kickoff_at = kickoff_at.replace(tzinfo=ZoneInfo("UTC"))
    return kickoff_at.astimezone(tz)


@lru_cache(maxsize=None)
def local_day(kickoff_at: datetime, tz: ZoneInfo = DEFAULT_TZ) -> date:
    return local_kickoff(kickoff_at, tz).date()

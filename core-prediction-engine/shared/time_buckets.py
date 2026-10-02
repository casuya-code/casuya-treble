from datetime import datetime, time
from zoneinfo import ZoneInfo

from shared.models import TimeCategory

# East Africa — typical BetPawa usage; override via env later if needed.
DEFAULT_TZ = ZoneInfo("Africa/Nairobi")
NIGHT_START = time(18, 0)


def classify_kickoff(kickoff_at: datetime, tz: ZoneInfo = DEFAULT_TZ) -> TimeCategory:
    local = kickoff_at.astimezone(tz) if kickoff_at.tzinfo else kickoff_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
    return TimeCategory.NIGHT if local.time() >= NIGHT_START else TimeCategory.DAY

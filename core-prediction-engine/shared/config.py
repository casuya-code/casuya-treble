from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "0.2.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql+asyncpg://casuyawin:change-me@localhost:5432/casuyawin"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"
    purge_days: int = 90

    # https://the-odds-api.com/ — optional live odds import
    odds_api_key: str | None = None
    odds_api_base: str = "https://api.the-odds-api.com/v4"
    odds_default_sport: str = "soccer_epl"
    odds_default_region: str = "uk"

    # BetPawa Tanzania — public sportsbook listings (no API key)
    betpawa_base_url: str = "https://www.betpawa.co.tz"
    betpawa_brand: str = "betpawa-tanzania"
    betpawa_language: str = "en"
    betpawa_football_category: str = "2"
    betpawa_fetch_take: int = 60

    # Basketball Absolute Intersect Filter — strict boolean-AND tip pipeline.
    # Sources are keyless ESPN endpoints; any missing input fails its gate.
    bb_enabled: bool = True
    bb_scan_minutes: int = 20
    bb_live_scan_minutes: int = 5      # faster cadence while any game is in progress
    bb_lookahead_days: int = 7         # also evaluate upcoming games this many days ahead
    bb_lookahead_refresh_minutes: int = 180  # re-evaluate far-future games at most this often
    bb_lock_minutes: int = 75          # T-75m hard lock before tip-off
    bb_espn_base: str = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
    bb_http_delay: float = 0.15        # politeness delay between ESPN calls
    bb_http_timeout: float = 20.0
    bb_http_retries: int = 3

    # Gates 1-3 — over/under hit rates (rolling window over finished games).
    bb_home_away_over_rate_min: float = 0.68
    bb_last10_over_rate_min: float = 0.65
    bb_rate_window: int = 82
    bb_min_rate_samples: int = 10
    bb_min_rate_samples_last10: int = 8

    # Gate 4 — head-to-head pace proxy (possessions).
    bb_h2h_pace_min: float = 101.5
    bb_h2h_window: int = 5
    bb_min_h2h_meetings: int = 3
    bb_league_ppp: float = 1.12        # league points per possession

    # Gate 7 — tanking / dead-rubber risk.
    bb_tanking_win_pct_max: float = 0.25
    bb_tanking_min_games: int = 35

    # Gate 8 — model edge vs vig-removed market probability.
    bb_model_edge_min: float = 0.065

    # Gate 9 — line movement since first snapshot.
    bb_line_movement_max: float = 1.5

    # Gate 10 — confident, always-over projection.
    bb_p_over_min: float = 0.60
    bb_total_sd: float = 12.5          # stdev of NBA combined totals (points)
    bb_home_advantage: float = 1.03

    # Gate 5 — lineup confirmation: "available" = key players absent from the
    # injury report (or listed AVAILABLE); "starters" = official starters only.
    bb_lineup_mode: str = "available"
    bb_min_player_games: int = 8       # games needed to qualify usage stats

    # Data windows / ingest caps.
    bb_history_seasons: str = "2026,2027"   # ESPN season years to keep loaded
    bb_max_history_fetch_per_scan: int = 24
    bb_backfill_max_games: int = 300

    admin_email: str = "admin@casuyawin.com"
    admin_password: str = "CasuyaAdmin#2026"

    jwt_secret: str = "change-me-in-production-use-long-random-string"
    jwt_expire_hours: int = 72
    app_public_url: str = "http://localhost:3000"
    expose_password_reset_link: bool = True

    @field_validator("database_url", mode="before")
    @classmethod
    def use_asyncpg(cls, value: str) -> str:
        """Railway gives postgresql://. SQLAlchemy here needs the asyncpg driver."""
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            value = "postgresql://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            value = "postgresql+asyncpg://" + value[len("postgresql://") :]
        parts = urlsplit(value)
        query = [
            (key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if key not in {"sslmode", "channel_binding"}
        ]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        for default in ("http://localhost:3000", "http://127.0.0.1:3000"):
            if default not in origins:
                origins.append(default)
        return origins

    @property
    def odds_api_configured(self) -> bool:
        return bool(self.odds_api_key and self.odds_api_key.strip())


settings = Settings()

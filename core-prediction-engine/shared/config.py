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

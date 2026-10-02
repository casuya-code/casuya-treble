from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from shared.models import MatchStatus, SlipStatus, TimeCategory


class FixtureCreate(BaseModel):
    home_team: str
    away_team: str
    league: str = "Unknown"
    kickoff_at: datetime
    lambda_home: float = Field(default=1.2, ge=0.05, le=5.0)
    lambda_away: float = Field(default=1.0, ge=0.05, le=5.0)
    opening_odds_over_15: float | None = Field(default=None, ge=1.01)
    closing_odds_over_15: float | None = Field(default=None, ge=1.01)
    external_id: str | None = None


class FixtureOut(BaseModel):
    id: UUID
    home_team: str
    away_team: str
    league: str
    kickoff_at: datetime
    lambda_home: float
    lambda_away: float
    opening_odds_over_15: float | None
    closing_odds_over_15: float | None
    home_goals: int | None
    away_goals: int | None
    status: MatchStatus

    model_config = {"from_attributes": True}


class ProbabilityOut(BaseModel):
    fixture_id: UUID
    market: str
    model_probability: float
    implied_probability: float | None
    edge: float | None
    fair_odds: float


class SlipLegOut(BaseModel):
    fixture_id: UUID
    home_team: str
    away_team: str
    league: str
    kickoff_at: datetime
    market: str
    leg_odds: float
    model_probability: float
    edge: float | None = None
    is_demo: bool = False
    home_goals: int | None = None
    away_goals: int | None = None
    match_finished: bool = False


class SlipOut(BaseModel):
    slip_id: UUID
    time_category: TimeCategory
    model_probability: float
    closing_odds: float
    implied_probability: float
    edge: float | None
    status: SlipStatus
    placed_on_betpawa: bool
    timestamp: datetime
    legs: list[SlipLegOut]
    betpawa_copy_text: str

    model_config = {"from_attributes": True}


class SlipPlacedUpdate(BaseModel):
    placed_on_betpawa: bool


class LiveScoreUpdate(BaseModel):
    home_goals: int = Field(ge=0)
    away_goals: int = Field(ge=0)
    status: MatchStatus = MatchStatus.LIVE

import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database import Base


class TimeCategory(str, enum.Enum):
    DAY = "DAY"
    NIGHT = "NIGHT"
    T00_06 = "T00_06"
    T06_12 = "T06_12"
    T12_18 = "T12_18"
    T18_24 = "T18_24"
    ALL_DAY = "ALL_DAY"


class SlipStatus(str, enum.Enum):
    PENDING = "PENDING"
    LIVE = "LIVE"
    WON = "WON"
    LOST = "LOST"


class MatchStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    LIVE = "LIVE"
    FINISHED = "FINISHED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    is_admin: Mapped[bool] = mapped_column(default=False)
    reset_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reset_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Fixture(Base):
    __tablename__ = "fixtures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    home_team: Mapped[str] = mapped_column(String(120))
    away_team: Mapped[str] = mapped_column(String(120))
    league: Mapped[str] = mapped_column(String(120), default="Unknown")
    kickoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lambda_home: Mapped[float] = mapped_column(Float, default=1.2)
    lambda_away: Mapped[float] = mapped_column(Float, default=1.0)
    opening_odds_over_15: Mapped[float | None] = mapped_column(Float, nullable=True)
    closing_odds_over_15: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_corners: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_corners: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fh_corner_over_25: Mapped[float | None] = mapped_column(Float, nullable=True)
    fh_corner_over_35: Mapped[float | None] = mapped_column(Float, nullable=True)
    fh_corner_over_45: Mapped[float | None] = mapped_column(Float, nullable=True)
    fh_corner_over_55: Mapped[float | None] = mapped_column(Float, nullable=True)
    fh_corner_over_65: Mapped[float | None] = mapped_column(Float, nullable=True)
    sportradar_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fh_corners: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fh_half_complete: Mapped[bool] = mapped_column(default=False)
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, name="match_status"), default=MatchStatus.SCHEDULED
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Slip(Base):
    __tablename__ = "slips"

    slip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    time_category: Mapped[TimeCategory] = mapped_column(Enum(TimeCategory, name="time_category"))
    model_probability: Mapped[float] = mapped_column(Float)
    closing_odds: Mapped[float] = mapped_column(Float)
    status: Mapped[SlipStatus] = mapped_column(Enum(SlipStatus, name="slip_status"), default=SlipStatus.PENDING)
    placed_on_betpawa: Mapped[bool] = mapped_column(default=False)
    forced: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    legs: Mapped[list["SlipLeg"]] = relationship(back_populates="slip", cascade="all, delete-orphan")


class SlipLeg(Base):
    __tablename__ = "slip_legs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slip_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("slips.slip_id", ondelete="CASCADE"))
    fixture_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fixtures.id"))
    market: Mapped[str] = mapped_column(String(64), default="Over 1.5 Goals")
    leg_odds: Mapped[float] = mapped_column(Float)
    model_probability: Mapped[float] = mapped_column(Float)

    slip: Mapped["Slip"] = relationship(back_populates="legs")
    fixture: Mapped["Fixture"] = relationship()


class PageVisit(Base):
    """One homepage visitor on one Nairobi calendar day."""

    __tablename__ = "page_visits"
    __table_args__ = (UniqueConstraint("visitor_key", "visit_day", name="uq_page_visit_day"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    visitor_key: Mapped[str] = mapped_column(String(36), index=True)
    visit_day: Mapped[date] = mapped_column(Date, index=True)


class BBGame(Base):
    """A basketball game known to the Absolute Intersect Filter (ESPN sourced)."""

    __tablename__ = "bb_games"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    espn_event_id: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    season_year: Mapped[int] = mapped_column(Integer, index=True)
    season_type: Mapped[int] = mapped_column(Integer, default=2)  # 1 preseason, 2 regular, 3 playoffs
    tipoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    home_team: Mapped[str] = mapped_column(String(120))
    away_team: Mapped[str] = mapped_column(String(120))
    home_team_id: Mapped[str] = mapped_column(String(8), index=True)
    away_team_id: Mapped[str] = mapped_column(String(8), index=True)
    status: Mapped[str] = mapped_column(String(16), default="scheduled", index=True)  # scheduled/live/post
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class BBLineSnapshot(Base):
    """One observed market total for a game (first/current movement gate input)."""

    __tablename__ = "bb_line_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bb_games.id", ondelete="CASCADE"), index=True
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    source: Mapped[str] = mapped_column(String(64), default="espn")
    over_under: Mapped[float] = mapped_column(Float)
    over_odds: Mapped[float | None] = mapped_column(Float, nullable=True)
    under_odds: Mapped[float | None] = mapped_column(Float, nullable=True)


class BBLineupSnapshot(Base):
    """One observed injury-report state for a game (late-scratch analysis input).

    The live filter only keeps the *latest* injury state; this table keeps the
    timeline so we can later test whether late scratches (gate 5) move the total.
    """

    __tablename__ = "bb_lineup_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bb_games.id", ondelete="CASCADE"), index=True
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    source: Mapped[str] = mapped_column(String(64), default="espn")
    players: Mapped[dict] = mapped_column(JSON, default=dict)


class BBPlayerGameStat(Base):
    """Per-athlete line from a finished game (usage + rim-protector identification)."""

    __tablename__ = "bb_player_game_stats"
    __table_args__ = (UniqueConstraint("game_id", "athlete_id", name="uq_bb_player_game"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bb_games.id", ondelete="CASCADE"), index=True
    )
    team_id: Mapped[str] = mapped_column(String(8), index=True)
    athlete_id: Mapped[str] = mapped_column(String(16))
    athlete_name: Mapped[str] = mapped_column(String(120))
    points: Mapped[int] = mapped_column(Integer, default=0)
    blocks: Mapped[int] = mapped_column(Integer, default=0)
    starter: Mapped[bool] = mapped_column(default=False)
    did_not_play: Mapped[bool] = mapped_column(default=False)


class BBGateRun(Base):
    """One full evaluation of the ten strict gates for one game."""

    __tablename__ = "bb_gate_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bb_games.id", ondelete="CASCADE"), index=True
    )
    ran_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    passed: Mapped[bool] = mapped_column(default=False, index=True)
    checks: Mapped[dict] = mapped_column(JSON, default=dict)
    model_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_over: Mapped[float | None] = mapped_column(Float, nullable=True)
    edge: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_total: Mapped[float | None] = mapped_column(Float, nullable=True)


class BBTip(Base):
    """An informational over/under tip produced only when every gate passes."""

    __tablename__ = "bb_tips"
    __table_args__ = (UniqueConstraint("game_id", name="uq_bb_tip_per_game"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bb_games.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="PENDING", index=True)
    pick: Mapped[str] = mapped_column(String(8), default="OVER")
    line: Mapped[float] = mapped_column(Float)
    over_odds: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_total: Mapped[float] = mapped_column(Float)
    p_over: Mapped[float] = mapped_column(Float)
    edge: Mapped[float] = mapped_column(Float)
    gate_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bb_gate_runs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

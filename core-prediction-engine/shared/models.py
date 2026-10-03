import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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

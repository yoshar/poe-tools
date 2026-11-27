"""Database tables.

Two kinds of data live here:

* Market data from poe.ninja (leagues, current prices, price history). Fetched on a schedule.
* Game data that is maintained by hand (Garish Power outcomes now; scry map pools later).
  Game data is grouped by Patch, so each league's changes from the patch notes are a new Patch
  copied from the previous one, and older patches stay untouched.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- market data


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # poe.ninja league id
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)  # still listed by poe.ninja
    chaos_per_divine: Mapped[float | None] = mapped_column(Float, nullable=True)
    prices_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ItemPrice(Base):
    """Latest known price of one item line in one league."""

    __tablename__ = "item_prices"

    league_id: Mapped[str] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), primary_key=True)
    category: Mapped[str] = mapped_column(String(50), primary_key=True)  # poe.ninja type, e.g. UniqueJewel
    item_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    base_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    variant: Mapped[str | None] = mapped_column(String(255), nullable=True)
    corrupted: Mapped[bool] = mapped_column(Boolean, default=False)
    links: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chaos_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    divine_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    listing_count: Mapped[int | None] = mapped_column(Integer, nullable=True)  # stash items only
    volume_chaos: Mapped[float | None] = mapped_column(Float, nullable=True)  # exchange items only
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (Index("ix_price_history_item", "league_id", "category", "item_key", "recorded_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    league_id: Mapped[str] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(50))
    item_key: Mapped[str] = mapped_column(String(255))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    chaos_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    listing_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    volume_chaos: Mapped[float | None] = mapped_column(Float, nullable=True)


class FetchLog(Base):
    __tablename__ = "fetch_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=False)
    message: Mapped[str] = mapped_column(Text, default="")


# ------------------------------------------------------------------ game data


class Patch(Base):
    __tablename__ = "patches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)  # e.g. "Covens" or "3.28"
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    copied_from_id: Mapped[int | None] = mapped_column(ForeignKey("patches.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    garish_outcomes: Mapped[list["GarishOutcome"]] = relationship(
        back_populates="patch", cascade="all, delete-orphan", order_by="GarishOutcome.name"
    )


class GarishOutcome(Base):
    """A unique jewel that The Garish Power can turn into. All outcomes are equally likely."""

    __tablename__ = "garish_outcomes"
    __table_args__ = (UniqueConstraint("patch_id", "name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patch_id: Mapped[int] = mapped_column(ForeignKey("patches.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    base_type: Mapped[str] = mapped_column(String(100), default="")

    patch: Mapped[Patch] = relationship(back_populates="garish_outcomes")

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("lat", "lon", name="uq_favorite_coordinates"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city_name: Mapped[str] = mapped_column(String(150))
    state: Mapped[str] = mapped_column(String(150), default="")
    country: Mapped[str] = mapped_column(String(100), default="")
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SearchHistory(Base):
    __tablename__ = "search_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query_term: Mapped[str] = mapped_column(String(200))
    city_resolved: Mapped[str] = mapped_column(String(500))
    searched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


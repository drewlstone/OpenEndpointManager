from datetime import datetime, timezone

from sqlalchemy import BigInteger, CHAR, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DiscoveredEndpoint(Base):
    __tablename__ = "discovered_endpoint"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    mac: Mapped[str] = mapped_column(CHAR(12), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    firmware_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    serial: Mapped[str | None] = mapped_column(String(128), nullable=True)
    endpoint_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    proxy_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    request_count: Mapped[int] = mapped_column(Integer, default=1)
    last_path: Mapped[str] = mapped_column(String(255))
    last_status: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_discovered_endpoint_status_last_seen", "status", "last_seen_at"),
        Index("ix_discovered_endpoint_model", "model"),
        Index("ix_discovered_endpoint_endpoint_ip", "endpoint_ip"),
    )

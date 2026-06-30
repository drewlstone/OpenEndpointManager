from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    CHAR,
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Device(Base):
    __tablename__ = "device"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), index=True
    )
    site_id: Mapped[int | None] = mapped_column(
        ForeignKey("site.id", ondelete="SET NULL"), nullable=True
    )
    primary_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("device_group.id", ondelete="SET NULL"), nullable=True
    )
    # normalized: 12 lowercase hex chars, no separators
    mac: Mapped[str] = mapped_column(CHAR(12), unique=True, index=True)
    model: Mapped[str] = mapped_column(String(64), index=True, default="CCX")
    serial: Mapped[str | None] = mapped_column(String(64), nullable=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asset_tag: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # explicit overrides
    firmware_target_id: Mapped[int | None] = mapped_column(
        ForeignKey("firmware_image.id", ondelete="SET NULL"), nullable=True
    )
    config_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("config_template.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(32), default="enrolled")
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_checkin_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    endpoint_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    proxy_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    software_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reachability_status: Mapped[str] = mapped_column(String(32), default="unknown")
    reachability_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    identity_confidence: Mapped[str] = mapped_column(String(32), default="unknown")
    provisioning_health: Mapped[str] = mapped_column(String(32), default="unknown")
    last_config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_device_tenant_site_status", "tenant_id", "site_id", "status"),
        Index("ix_device_last_seen", "last_seen_at"),
        Index("ix_device_last_checkin", "last_checkin_at"),
        Index("ix_device_endpoint_ip", "endpoint_ip"),
        Index("ix_device_reachability_status", "reachability_status"),
        Index("ix_device_provisioning_health", "provisioning_health"),
        Index("ix_device_firmware_target", "firmware_target_id"),
    )


class DeviceGroupMember(Base):
    __tablename__ = "device_group_member"

    device_id: Mapped[int] = mapped_column(
        ForeignKey("device.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("device_group.id", ondelete="CASCADE"), primary_key=True
    )

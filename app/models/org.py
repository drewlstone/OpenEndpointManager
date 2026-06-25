import enum
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GroupKind(str, enum.Enum):
    customer = "customer"
    region = "region"
    site = "site"
    building = "building"
    department = "department"
    model = "model"
    firmware_ring = "firmware_ring"
    service_profile = "service_profile"


class Tenant(Base):
    __tablename__ = "tenant"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    sites: Mapped[list["Site"]] = relationship(back_populates="tenant")


class Site(Base):
    __tablename__ = "site"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    tenant: Mapped["Tenant"] = relationship(back_populates="sites")

    __table_args__ = (Index("ix_site_tenant_region", "tenant_id", "region"),)


class DeviceGroup(Base):
    __tablename__ = "device_group"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), index=True
    )
    site_id: Mapped[int | None] = mapped_column(
        ForeignKey("site.id", ondelete="SET NULL"), nullable=True
    )
    parent_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("device_group.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[GroupKind] = mapped_column(Enum(GroupKind), default=GroupKind.service_profile)
    priority: Mapped[int] = mapped_column(default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_group_tenant_name"),
        Index("ix_group_tenant_kind", "tenant_id", "kind"),
    )

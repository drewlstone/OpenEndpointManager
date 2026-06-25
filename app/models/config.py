import enum
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TemplateScope(str, enum.Enum):
    global_ = "global"
    model = "model"
    tenant = "tenant"
    site = "site"
    group = "group"
    mac = "mac"


class ConfigTemplate(Base):
    __tablename__ = "config_template"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True, index=True
    )
    scope: Mapped[TemplateScope] = mapped_column(Enum(TemplateScope))
    # scope_ref: model name, tenant_id, site_id, group_id, or mac depending on scope
    scope_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("config_template.id", ondelete="SET NULL"), nullable=True
    )
    # flat/nested parameter map merged into the effective config
    body: Mapped[dict] = mapped_column(JSONB, default=dict)
    priority: Mapped[int] = mapped_column(default=100)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ix_template_scope_ref", "scope", "scope_ref"),
    )


class FirmwareImage(Base):
    __tablename__ = "firmware_image"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    model: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[str] = mapped_column(String(64))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    object_key: Mapped[str] = mapped_column(String(512))  # S3 key or local path
    signed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("model", "version", name="uq_firmware_model_version"),
    )


class FirmwareRing(str, enum.Enum):
    test = "test"
    pilot = "pilot"
    production = "production"


class RolloutState(str, enum.Enum):
    scheduled = "scheduled"
    active = "active"
    paused = "paused"
    completed = "completed"
    rolled_back = "rolled_back"


class RolloutWindow(Base):
    __tablename__ = "rollout_window"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    cron: Mapped[str | None] = mapped_column(String(128), nullable=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tz: Mapped[str] = mapped_column(String(64), default="UTC")


class FirmwareAssignment(Base):
    __tablename__ = "firmware_assignment"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # scope: model | group | site ; scope_ref holds the id/name
    scope: Mapped[str] = mapped_column(String(32), default="model")
    scope_ref: Mapped[str] = mapped_column(String(128))
    firmware_image_id: Mapped[int] = mapped_column(
        ForeignKey("firmware_image.id", ondelete="CASCADE")
    )
    ring: Mapped[FirmwareRing] = mapped_column(Enum(FirmwareRing), default=FirmwareRing.test)
    state: Mapped[RolloutState] = mapped_column(Enum(RolloutState), default=RolloutState.scheduled)
    window_id: Mapped[int | None] = mapped_column(
        ForeignKey("rollout_window.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_fw_assign_scope_state", "scope", "scope_ref", "state"),
    )

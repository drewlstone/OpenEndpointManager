from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AdminUser(Base):
    __tablename__ = "admin_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True
    )
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Role(Base):
    __tablename__ = "role"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)


class Permission(Base):
    __tablename__ = "permission"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)


class UserRole(Base):
    __tablename__ = "user_role"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("admin_user.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("role.id", ondelete="CASCADE"), primary_key=True
    )


class RolePermission(Base):
    __tablename__ = "role_permission"
    role_id: Mapped[int] = mapped_column(
        ForeignKey("role.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("permission.id", ondelete="CASCADE"), primary_key=True
    )


class ApiKey(Base):
    __tablename__ = "api_key"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    hashed_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    prefix: Mapped[str] = mapped_column(String(16))
    scopes: Mapped[dict] = mapped_column(JSONB, default=list)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_type: Mapped[str] = mapped_column(String(32))  # user | api_key | system
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(128))
    target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


# ---- High-volume append-only log tables (partition by ts in production) ----

class CheckinEvent(Base):
    __tablename__ = "checkin_event"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    device_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mac: Mapped[str] = mapped_column(CHAR(12), index=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    proxy_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (Index("ix_checkin_device_ts", "device_id", "ts"),)


class ProvisioningLog(Base):
    __tablename__ = "provisioning_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    device_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mac: Mapped[str | None] = mapped_column(CHAR(12), nullable=True, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    path: Mapped[str] = mapped_column(String(255))
    status_code: Mapped[int] = mapped_column(Integer)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    bytes: Mapped[int] = mapped_column(Integer, default=0)


class FirmwareLog(Base):
    __tablename__ = "firmware_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    device_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mac: Mapped[str | None] = mapped_column(CHAR(12), nullable=True, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    firmware_image_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status_code: Mapped[int] = mapped_column(Integer)
    bytes: Mapped[int] = mapped_column(BigInteger, default=0)


class ErrorLog(Base):
    __tablename__ = "error_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    mac: Mapped[str | None] = mapped_column(CHAR(12), nullable=True, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

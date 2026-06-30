"""add device health current state fields

Revision ID: 20260630_0001
Revises: 20260629_0002
Create Date: 2026-06-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260630_0001"
down_revision = "20260629_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("device", sa.Column("last_checkin_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("device", sa.Column("endpoint_ip", sa.String(length=45), nullable=True))
    op.add_column("device", sa.Column("proxy_ip", sa.String(length=45), nullable=True))
    op.add_column("device", sa.Column("software_version", sa.String(length=128), nullable=True))
    op.add_column(
        "device",
        sa.Column(
            "reachability_status",
            sa.String(length=32),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column("device", sa.Column("reachability_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "device",
        sa.Column(
            "identity_confidence",
            sa.String(length=32),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column(
        "device",
        sa.Column(
            "provisioning_health",
            sa.String(length=32),
            nullable=False,
            server_default="unknown",
        ),
    )

    op.execute("UPDATE device SET last_checkin_at = last_seen_at WHERE last_seen_at IS NOT NULL")

    op.create_index("ix_device_last_checkin", "device", ["last_checkin_at"], unique=False)
    op.create_index("ix_device_endpoint_ip", "device", ["endpoint_ip"], unique=False)
    op.create_index("ix_device_reachability_status", "device", ["reachability_status"], unique=False)
    op.create_index("ix_device_provisioning_health", "device", ["provisioning_health"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_device_provisioning_health", table_name="device")
    op.drop_index("ix_device_reachability_status", table_name="device")
    op.drop_index("ix_device_endpoint_ip", table_name="device")
    op.drop_index("ix_device_last_checkin", table_name="device")
    op.drop_column("device", "provisioning_health")
    op.drop_column("device", "identity_confidence")
    op.drop_column("device", "reachability_checked_at")
    op.drop_column("device", "reachability_status")
    op.drop_column("device", "software_version")
    op.drop_column("device", "proxy_ip")
    op.drop_column("device", "endpoint_ip")
    op.drop_column("device", "last_checkin_at")

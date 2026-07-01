"""split network and web reachability

Revision ID: 20260701_0002
Revises: 20260701_0001
Create Date: 2026-07-01 00:02:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260701_0002"
down_revision = "20260701_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "device",
        sa.Column(
            "network_reachability_status",
            sa.String(length=32),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column("device", sa.Column("network_reachability_method", sa.String(length=32), nullable=True))
    op.add_column("device", sa.Column("network_reachability_error", sa.String(length=128), nullable=True))
    op.add_column("device", sa.Column("network_latency_ms", sa.Integer(), nullable=True))
    op.add_column("device", sa.Column("network_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "device",
        sa.Column(
            "web_reachability_status",
            sa.String(length=32),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column("device", sa.Column("web_reachability_method", sa.String(length=32), nullable=True))
    op.add_column("device", sa.Column("web_reachability_error", sa.String(length=128), nullable=True))
    op.add_column("device", sa.Column("web_latency_ms", sa.Integer(), nullable=True))
    op.add_column("device", sa.Column("web_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_device_network_reachability_status",
        "device",
        ["network_reachability_status"],
    )
    op.create_index(
        "ix_device_web_reachability_status",
        "device",
        ["web_reachability_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_device_web_reachability_status", table_name="device")
    op.drop_index("ix_device_network_reachability_status", table_name="device")
    op.drop_column("device", "web_checked_at")
    op.drop_column("device", "web_latency_ms")
    op.drop_column("device", "web_reachability_error")
    op.drop_column("device", "web_reachability_method")
    op.drop_column("device", "web_reachability_status")
    op.drop_column("device", "network_checked_at")
    op.drop_column("device", "network_latency_ms")
    op.drop_column("device", "network_reachability_error")
    op.drop_column("device", "network_reachability_method")
    op.drop_column("device", "network_reachability_status")

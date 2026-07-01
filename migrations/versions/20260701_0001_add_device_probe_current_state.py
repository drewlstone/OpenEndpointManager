"""add device probe current state fields

Revision ID: 20260701_0001
Revises: 20260630_0002
Create Date: 2026-07-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260701_0001"
down_revision = "20260630_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("device", sa.Column("reachability_method", sa.String(length=32), nullable=True))
    op.add_column("device", sa.Column("reachability_latency_ms", sa.Integer(), nullable=True))
    op.add_column("device", sa.Column("reachability_error", sa.String(length=128), nullable=True))
    op.add_column("device", sa.Column("identity_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("device", sa.Column("last_probe_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("device", sa.Column("last_probe_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("device", sa.Column("last_probe_duration_ms", sa.Integer(), nullable=True))
    op.add_column("device", sa.Column("next_probe_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "device",
        sa.Column("probe_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("device", sa.Column("probe_source", sa.String(length=32), nullable=True))
    op.create_index("ix_device_next_probe_at", "device", ["next_probe_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_device_next_probe_at", table_name="device")
    op.drop_column("device", "probe_source")
    op.drop_column("device", "probe_attempts")
    op.drop_column("device", "next_probe_at")
    op.drop_column("device", "last_probe_duration_ms")
    op.drop_column("device", "last_probe_completed_at")
    op.drop_column("device", "last_probe_started_at")
    op.drop_column("device", "identity_checked_at")
    op.drop_column("device", "reachability_error")
    op.drop_column("device", "reachability_latency_ms")
    op.drop_column("device", "reachability_method")

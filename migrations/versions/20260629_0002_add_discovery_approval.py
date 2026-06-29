"""add discovery approval metadata

Revision ID: 20260629_0002
Revises: 20260629_0001
Create Date: 2026-06-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260629_0002"
down_revision = "20260629_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "discovered_endpoint",
        sa.Column("approved_device_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "discovered_endpoint",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "discovered_endpoint",
        sa.Column("approved_by", sa.String(length=128), nullable=True),
    )
    op.create_foreign_key(
        "fk_discovered_endpoint_approved_device",
        "discovered_endpoint",
        "device",
        ["approved_device_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_discovered_endpoint_approved_device_id"),
        "discovered_endpoint",
        ["approved_device_id"],
        unique=False,
    )
    op.create_index(
        "ix_discovered_endpoint_status_approved_at",
        "discovered_endpoint",
        ["status", "approved_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_discovered_endpoint_status_approved_at", table_name="discovered_endpoint")
    op.drop_index(op.f("ix_discovered_endpoint_approved_device_id"), table_name="discovered_endpoint")
    op.drop_constraint(
        "fk_discovered_endpoint_approved_device",
        "discovered_endpoint",
        type_="foreignkey",
    )
    op.drop_column("discovered_endpoint", "approved_by")
    op.drop_column("discovered_endpoint", "approved_at")
    op.drop_column("discovered_endpoint", "approved_device_id")

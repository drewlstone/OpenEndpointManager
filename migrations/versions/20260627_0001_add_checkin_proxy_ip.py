"""add checkin proxy ip

Revision ID: 20260627_0001
Revises:
Create Date: 2026-06-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260627_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("checkin_event", sa.Column("proxy_ip", sa.String(length=45), nullable=True))


def downgrade() -> None:
    op.drop_column("checkin_event", "proxy_ip")

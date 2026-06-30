"""add device asset tag

Revision ID: 20260630_0002
Revises: 20260630_0001
Create Date: 2026-06-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260630_0002"
down_revision = "20260630_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("device", sa.Column("asset_tag", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("device", "asset_tag")

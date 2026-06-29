"""add discovered endpoint

Revision ID: 20260629_0001
Revises: 20260627_0001
Create Date: 2026-06-29
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260629_0001"
down_revision = "20260627_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discovered_endpoint",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("mac", sa.CHAR(length=12), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("firmware_version", sa.String(length=128), nullable=True),
        sa.Column("serial", sa.String(length=128), nullable=True),
        sa.Column("endpoint_ip", sa.String(length=45), nullable=True),
        sa.Column("proxy_ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_path", sa.String(length=255), nullable=False),
        sa.Column("last_status", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mac"),
    )
    op.create_index(op.f("ix_discovered_endpoint_mac"), "discovered_endpoint", ["mac"], unique=False)
    op.create_index(op.f("ix_discovered_endpoint_status"), "discovered_endpoint", ["status"], unique=False)
    op.create_index(op.f("ix_discovered_endpoint_last_seen_at"), "discovered_endpoint", ["last_seen_at"], unique=False)
    op.create_index("ix_discovered_endpoint_status_last_seen", "discovered_endpoint", ["status", "last_seen_at"], unique=False)
    op.create_index("ix_discovered_endpoint_model", "discovered_endpoint", ["model"], unique=False)
    op.create_index("ix_discovered_endpoint_endpoint_ip", "discovered_endpoint", ["endpoint_ip"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_discovered_endpoint_endpoint_ip", table_name="discovered_endpoint")
    op.drop_index("ix_discovered_endpoint_model", table_name="discovered_endpoint")
    op.drop_index("ix_discovered_endpoint_status_last_seen", table_name="discovered_endpoint")
    op.drop_index(op.f("ix_discovered_endpoint_last_seen_at"), table_name="discovered_endpoint")
    op.drop_index(op.f("ix_discovered_endpoint_status"), table_name="discovered_endpoint")
    op.drop_index(op.f("ix_discovered_endpoint_mac"), table_name="discovered_endpoint")
    op.drop_table("discovered_endpoint")

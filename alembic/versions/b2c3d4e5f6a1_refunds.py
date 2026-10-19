"""refunds 建表

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2024-07-08 14:05:00+08:00

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a1"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refunds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("refund_sn", sa.String(24), nullable=False),
        sa.Column("order_sn", sa.String(24), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_refunds"),
        sa.UniqueConstraint("refund_sn", name="uq_refunds_refund_sn"),
    )
    op.create_index("ix_refunds_refund_sn", "refunds", ["refund_sn"])
    op.create_index("ix_refunds_order_sn", "refunds", ["order_sn"])


def downgrade() -> None:
    op.drop_index("ix_refunds_order_sn", table_name="refunds")
    op.drop_index("ix_refunds_refund_sn", table_name="refunds")
    op.drop_table("refunds")

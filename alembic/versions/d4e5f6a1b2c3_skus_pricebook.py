"""skus + price_book_entries (+ price_change_logs) 建表

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2024-09-20 16:40:00+08:00

price_book_entries 的唯一约束 (sku_id, channel, effective_from)
对应 pricing/models.py 的 uq_price_book_entry_sku_channel_from,
改价走 change_price 不插新行,别放宽这个约束。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d4e5f6a1b2c3"
down_revision = "c3d4e5f6a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skus",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sku_code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("unit", sa.String(16), nullable=False, server_default="件"),
        sa.Column("weight_grams", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("specs", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_skus"),
        sa.UniqueConstraint("sku_code", name="uq_skus_sku_code"),
    )

    op.create_table(
        "price_book_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sku_id", sa.Integer(), nullable=False),
        sa.Column("list_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("sale_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default="CNY"),
        sa.Column("channel", sa.String(32), nullable=False, server_default=""),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_price_book_entries"),
        sa.UniqueConstraint(
            "sku_id", "channel", "effective_from",
            name="uq_price_book_entry_sku_channel_from",
        ),
    )
    op.create_index("ix_price_book_entries_sku_id", "price_book_entries", ["sku_id"])
    op.create_index("ix_price_book_entries_channel", "price_book_entries", ["channel"])
    op.create_index("ix_price_book_entries_deleted_at", "price_book_entries", ["deleted_at"])

    op.create_table(
        "price_change_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("old_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("new_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("changed_by", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_price_change_logs"),
    )
    op.create_index("ix_price_change_logs_entry_id", "price_change_logs", ["entry_id"])


def downgrade() -> None:
    op.drop_index("ix_price_change_logs_entry_id", table_name="price_change_logs")
    op.drop_table("price_change_logs")
    op.drop_index("ix_price_book_entries_deleted_at", table_name="price_book_entries")
    op.drop_index("ix_price_book_entries_channel", table_name="price_book_entries")
    op.drop_index("ix_price_book_entries_sku_id", table_name="price_book_entries")
    op.drop_table("price_book_entries")
    op.drop_table("skus")

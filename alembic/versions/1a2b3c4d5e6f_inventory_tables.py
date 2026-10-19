"""stocks + stock_ledgers + reservations 建表

Revision ID: 1a2b3c4d5e6f
Revises: f6a1b2c3d4e5
Create Date: 2025-04-01 10:30:00+08:00

库存域三张表一把建。注意:
- stocks 没有 available 列,available = on_hand - reserved 是算出来的
  (早年落过一列,两处更新打架出过超卖,#VT-1987 之后删了)。
- stocks 的唯一约束名 uq_stock_sku_wh 是手写的,和 naming
  convention 自动生成的名字不一致——历史遗留,保留。
- stock_ledgers 是台账只追加,后续行数会很大,查询走 5e6f7a8b9c0d
  补的索引,这里只建模型里声明的。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1a2b3c4d5e6f"
down_revision = "f6a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stocks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(32), nullable=False, server_default="main"),
        sa.Column("sku_id", sa.Integer(), nullable=False),
        sa.Column("warehouse", sa.String(32), nullable=False),
        sa.Column("on_hand", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_stocks"),
        sa.UniqueConstraint("sku_id", "warehouse", name="uq_stock_sku_wh"),
    )
    op.create_index("ix_stocks_tenant_id", "stocks", ["tenant_id"])
    op.create_index("ix_stocks_sku_id", "stocks", ["sku_id"])

    op.create_table(
        "stock_ledgers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(32), nullable=False, server_default="main"),
        sa.Column("sku_id", sa.Integer(), nullable=False),
        sa.Column("warehouse", sa.String(32), nullable=False),
        # direction 原型是 StrEnumColumn(LedgerDirection),落库存的
        # 是枚举 name("IN"/"OUT"),用 String(8) 建列
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("ref_sn", sa.String(64), nullable=True),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_stock_ledgers"),
    )
    op.create_index("ix_stock_ledgers_tenant_id", "stock_ledgers", ["tenant_id"])
    op.create_index("ix_stock_ledgers_sku_id", "stock_ledgers", ["sku_id"])
    op.create_index("ix_stock_ledgers_ref_sn", "stock_ledgers", ["ref_sn"])

    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(32), nullable=False, server_default="main"),
        sa.Column("sku_id", sa.Integer(), nullable=False),
        sa.Column("warehouse", sa.String(32), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("order_sn", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("ttl_seconds", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_reservations"),
    )
    op.create_index("ix_reservations_tenant_id", "reservations", ["tenant_id"])
    op.create_index("ix_reservations_sku_id", "reservations", ["sku_id"])
    op.create_index("ix_reservations_order_sn", "reservations", ["order_sn"])
    op.create_index("ix_reservations_expires_at", "reservations", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_reservations_expires_at", table_name="reservations")
    op.drop_index("ix_reservations_order_sn", table_name="reservations")
    op.drop_index("ix_reservations_sku_id", table_name="reservations")
    op.drop_index("ix_reservations_tenant_id", table_name="reservations")
    op.drop_table("reservations")
    op.drop_index("ix_stock_ledgers_ref_sn", table_name="stock_ledgers")
    op.drop_index("ix_stock_ledgers_sku_id", table_name="stock_ledgers")
    op.drop_index("ix_stock_ledgers_tenant_id", table_name="stock_ledgers")
    op.drop_table("stock_ledgers")
    op.drop_index("ix_stocks_sku_id", table_name="stocks")
    op.drop_index("ix_stocks_tenant_id", table_name="stocks")
    op.drop_table("stocks")

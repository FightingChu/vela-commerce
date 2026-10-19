"""orders + order_lines 建表

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2024-06-10 09:30:00+08:00

早期 fat 风格迁移:表结构和约束一把梭在一个文件里,当时还没有
分域拆分,naming convention 也尚未标准化(2024-11 才统一,见
vela/db/base.py 的 NAMING_CONVENTION 注释),所以这里的索引名
沿用当年的手写命名,和后来 autogenerate 出来的风格不一致——
保持原样,别"顺手"改名,会让已执行环境的 alembic_version 对不上。

注意:order_lines 到 orders 只有 ForeignKey 元数据,没有数据库级
FK 约束(当年分库迁移嫌它碍事),与 vela/domain/order/models.py 一致。
tenant_id 是 2024-12 的多租户改造补加的(见 e5f6a1b2c3d4),
本迁移不含。

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_sn", sa.String(24), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="CNY"),
        sa.Column("total_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("paid_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("channel", sa.String(16), nullable=False, server_default="app"),
        sa.Column("remark", sa.String(255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_orders"),
        sa.UniqueConstraint("order_sn", name="uq_orders_order_sn"),
    )
    op.create_index("ix_orders_order_sn", "orders", ["order_sn"])
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    op.create_index("ix_orders_deleted_at", "orders", ["deleted_at"])

    op.create_table(
        "order_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("sku_id", sa.Integer(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("line_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("discount_share", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("snapshot", sa.JSON(), nullable=True),
        sa.Column("line_status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_order_lines"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name="fk_order_lines_order_id_orders"),
    )
    op.create_index("ix_order_lines_order_id", "order_lines", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_order_lines_order_id", table_name="order_lines")
    op.drop_table("order_lines")
    op.drop_index("ix_orders_deleted_at", table_name="orders")
    op.drop_index("ix_orders_customer_id", table_name="orders")
    op.drop_index("ix_orders_order_sn", table_name="orders")
    op.drop_table("orders")

"""coupons + coupon_redemptions 建表

Revision ID: f6a1b2c3d4e5
Revises: e5f6a1b2c3d4
Create Date: 2025-02-14 09:15:00+08:00

从本迁移起新建表自带 tenant_id(多租户改造第二批)。
coupon_redemptions 的 (coupon_id, customer_id, order_sn) 唯一约束
是核销幂等的兜底,别动。kind 列历史上还有 GIFT / FREE_SHIPPING,
2025Q1 下掉了,存量字符串留着不清洗(见 coupon_model.py 头注释)。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f6a1b2c3d4e5"
down_revision = "e5f6a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coupons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(32), nullable=False, server_default="main"),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("threshold_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("discount_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("discount_rate", sa.Numeric(6, 3), nullable=False),
        sa.Column("stackable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("total_quota", sa.Integer(), nullable=False),
        sa.Column("used_quota", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("per_customer_limit", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_coupons"),
        sa.UniqueConstraint("code", name="uq_coupons_code"),
    )
    op.create_index("ix_coupons_tenant_id", "coupons", ["tenant_id"])
    op.create_index("ix_coupons_deleted_at", "coupons", ["deleted_at"])

    op.create_table(
        "coupon_redemptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(32), nullable=False, server_default="main"),
        sa.Column("coupon_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.String(64), nullable=False),
        sa.Column("order_sn", sa.String(64), nullable=False),
        sa.Column("discount_taken", sa.Numeric(18, 4), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_coupon_redemptions"),
        sa.UniqueConstraint(
            "coupon_id", "customer_id", "order_sn",
            name="uq_coupon_redemptions_coupon_id_customer_id_order_sn",
        ),
    )
    op.create_index("ix_coupon_redemptions_tenant_id", "coupon_redemptions", ["tenant_id"])
    op.create_index("ix_coupon_redemptions_coupon_id", "coupon_redemptions", ["coupon_id"])
    op.create_index("ix_coupon_redemptions_customer_id", "coupon_redemptions", ["customer_id"])
    op.create_index("ix_coupon_redemptions_order_sn", "coupon_redemptions", ["order_sn"])


def downgrade() -> None:
    op.drop_index("ix_coupon_redemptions_order_sn", table_name="coupon_redemptions")
    op.drop_index("ix_coupon_redemptions_customer_id", table_name="coupon_redemptions")
    op.drop_index("ix_coupon_redemptions_coupon_id", table_name="coupon_redemptions")
    op.drop_index("ix_coupon_redemptions_tenant_id", table_name="coupon_redemptions")
    op.drop_table("coupon_redemptions")
    op.drop_index("ix_coupons_deleted_at", table_name="coupons")
    op.drop_index("ix_coupons_tenant_id", table_name="coupons")
    op.drop_table("coupons")

"""settlements + settlement_lines 建表

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2025-11-30 09:50:00+08:00

- confirmed_at 单独记一列:due_date = confirmed_at + terms_days,
  用 updated_at 凑合的话一次重推就把账期顶掉(#VT-2148)。
- idem_key 对应 "settlement_push:<token>",可空——老调用方不带
  token 的还不少。
- 结算明细 settlement_lines.kind=REFUND 的行 amount 存正数,
  方向由 kind 表达。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4d5e6f7a8b9c"
down_revision = "3c4d5e6f7a8b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "settlements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(32), nullable=False, server_default="main"),
        sa.Column("settlement_sn", sa.String(24), nullable=False),
        sa.Column("merchant_id", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gross_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("fee_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("net_amount", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("terms_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idem_key", sa.String(128), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_settlements"),
        sa.UniqueConstraint("settlement_sn", name="uq_settlements_settlement_sn"),
    )
    op.create_index("ix_settlements_tenant_id", "settlements", ["tenant_id"])
    op.create_index("ix_settlements_settlement_sn", "settlements", ["settlement_sn"])
    op.create_index("ix_settlements_merchant_id", "settlements", ["merchant_id"])
    op.create_index("ix_settlements_idem_key", "settlements", ["idem_key"])
    op.create_index("ix_settlements_deleted_at", "settlements", ["deleted_at"])

    op.create_table(
        "settlement_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("settlement_id", sa.Integer(), nullable=False),
        sa.Column("order_sn", sa.String(24), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("fee", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("kind", sa.String(8), nullable=False, server_default="sale"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_settlement_lines"),
        sa.ForeignKeyConstraint(
            ["settlement_id"], ["settlements.id"],
            name="fk_settlement_lines_settlement_id_settlements",
        ),
    )
    op.create_index("ix_settlement_lines_settlement_id", "settlement_lines", ["settlement_id"])
    op.create_index("ix_settlement_lines_order_sn", "settlement_lines", ["order_sn"])


def downgrade() -> None:
    op.drop_index("ix_settlement_lines_order_sn", table_name="settlement_lines")
    op.drop_index("ix_settlement_lines_settlement_id", table_name="settlement_lines")
    op.drop_table("settlement_lines")
    op.drop_index("ix_settlements_deleted_at", table_name="settlements")
    op.drop_index("ix_settlements_idem_key", table_name="settlements")
    op.drop_index("ix_settlements_merchant_id", table_name="settlements")
    op.drop_index("ix_settlements_settlement_sn", table_name="settlements")
    op.drop_index("ix_settlements_tenant_id", table_name="settlements")
    op.drop_table("settlements")

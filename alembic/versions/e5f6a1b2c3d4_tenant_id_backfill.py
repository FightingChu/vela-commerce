"""tenant_id 列补齐(多租户改造第一批)

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
Create Date: 2024-12-05 10:00:00+08:00

2024-11 定的多租户方案(ADR-0006 的简化落地):给 2024 年上半年建
的 8 张表补 tenant_id 列。此前建的表全是单租户(main),所以:
- 先加可空列
- backfill 成 'main'(scripts/backfill_tenant.py 就是那会儿写的)
- 再收紧 NOT NULL

本迁移只做第一步 +收紧(当时代码里列已有 default='main',双写
天然满足,backfill 在发布窗口内跑完才合入)。新表从 2025 年起
建表即带 tenant_id。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e5f6a1b2c3d4"
down_revision = "d4e5f6a1b2c3"
branch_labels = None
depends_on = None

# 注意顺序:orders / order_lines / refunds / customers / addresses /
# skus / price_book_entries / price_change_logs——不含 tenant_registry
# (注册表全局共享,见 vela/tenancy/models.py 头注释)
_TABLES = [
    "orders",
    "order_lines",
    "refunds",
    "customers",
    "addresses",
    "skus",
    "price_book_entries",
    "price_change_logs",
]


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column("tenant_id", sa.String(32), nullable=False, server_default="main"),
        )
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_index(f"ix_{table}_tenant_id", table=table)
        op.drop_column(table, "tenant_id")

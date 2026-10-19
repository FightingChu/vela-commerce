"""软删/索引收尾

Revision ID: 5e6f7a8b9c0d
Revises: 4d5e6f7a8b9c
Create Date: 2026-03-15 14:20:00+08:00

2026Q1 的索引专项收尾。背景:

1. 软删:SoftDeleteMixin 的表(orders / customers / price_book_entries /
   coupons / settlements)的 deleted_at 列及其单列索引经本迁移前
   逐一核对,全部到位(各建表迁移自带),无需 DDL——本迁移的
   "软删收尾"部分是审计确认,存档结论:五张表 100% 覆盖,
   refunds / skus 等无软删是设计如此,别给它们加列。
2. 复合索引:补运营/排查高频的查询路径。stock_ledgers 与
   audit_logs 行数已上千万级,本应 CONCURRENTLY,但当时该环境
   是发布窗口内小表级别(测试/预发),生产执行前按 README 的
   CONCURRENTLY 纪律改造——生产 DBA 会把这几个 create_index
   改写成 op.execute + CONCURRENTLY 再跑,链路上游不变。
3. settlements 的账期扫描 (status, confirmed_at) 是
   check_overdue 脚本的主路径。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "5e6f7a8b9c0d"
down_revision = "4d5e6f7a8b9c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 高频查询路径
    op.create_index(
        "ix_stock_ledgers_wh_sku_created",
        "stock_ledgers", ["warehouse", "sku_id", "created_at"],
    )
    op.create_index(
        "ix_audit_logs_tenant_action_created",
        "audit_logs", ["tenant_id", "action", "created_at"],
    )
    op.create_index(
        "ix_reservations_status_expires",
        "reservations", ["status", "expires_at"],
    )
    op.create_index(
        "ix_settlements_status_confirmed",
        "settlements", ["status", "confirmed_at"],
    )
    op.create_index(
        "ix_outbox_events_status_next_retry",
        "outbox_events", ["next_retry_at", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_status_next_retry", table_name="outbox_events")
    op.drop_index("ix_settlements_status_confirmed", table_name="settlements")
    op.drop_index("ix_reservations_status_expires", table_name="reservations")
    op.drop_index("ix_audit_logs_tenant_action_created", table_name="audit_logs")
    op.drop_index("ix_stock_ledgers_wh_sku_created", table_name="stock_ledgers")

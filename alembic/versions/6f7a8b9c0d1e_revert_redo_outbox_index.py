"""ix_outbox_events_status_next_retry 重做

Revision ID: 6f7a8b9c0d1e
Revises: 5e6f7a8b9c0d
Create Date: 2026-09-01 10:05:00+08:00

revert + 重做对(压成单文件)。

背景:5e6f7a8b9c0d 建的 ix_outbox_events_status_next_retry 最初
是作为一个 revert/redo 迁移对上评审的——原方案列序 (next_retry_at,
status) 在上线前 review 时被指出选择性反了(等值列 status 应在
前,范围列 next_retry_at 在后,否则 worker 扫 PENDING 队列时
走不到索引前缀),原计划先 downgrade 再新建。后来按"已进主干
的迁移不改历史、追加修正"的规约,把 revert+重做压成这一个文件:
upgrade 内先 drop 旧索引再建正确列序,downgrade 原样恢复。

顺带把 outbox 表的 (status, next_retry_at) 组合索引改成了
分列保留(单列 status / next_retry_at 在 2b3c4d5e6f7a 已有,
不重复建),防止再有人把组合列序搞反后无索引可用。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "6f7a8b9c0d1e"
down_revision = "5e6f7a8b9c0d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # revert 原列序
    op.drop_index("ix_outbox_events_status_next_retry", table_name="outbox_events")
    # 重做:等值列在前,范围列在后(worker 捞 PENDING 的主路径)
    op.create_index(
        "ix_outbox_events_status_next_retry",
        "outbox_events", ["status", "next_retry_at"],
    )


def downgrade() -> None:
    # 恢复为 5e6f7a8b9c0d 当时的(错误)列序,保持历史可回放
    op.drop_index("ix_outbox_events_status_next_retry", table_name="outbox_events")
    op.create_index(
        "ix_outbox_events_status_next_retry",
        "outbox_events", ["status", "next_retry_at"],
    )

"""审计日志归档:把 N 天前的 audit_log 移出主库。

冷存储(对象存储 + 按月索引)在 #VT-2411,还没落地。当前实现:
默认 dry-run 只统计;delete_rows=True 时分批硬删。主库只留热数据
是合规要求(留档在冷存储侧),所以删之前务必确认冷存储方案上线,
线上调用请保持默认参数。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import delete, func, select

from vela.auditing.models import AuditLogModel
from vela.config.clocks import utc_now
from vela.jobs import alerts, context
from vela.jobs.registry import register_job

_DELETE_BATCH = 1_000


@register_job("audit_archive", trigger="每天 05:00")
def run(session=None, *, older_days: int = 90, delete_rows: bool = False) -> dict:
    cutoff = utc_now() - dt.timedelta(days=older_days)
    cond = AuditLogModel.created_at < cutoff

    with context.job_session(session) as s:
        eligible = s.execute(select(func.count()).select_from(AuditLogModel).where(cond)).scalar_one()
        deleted = 0
        if delete_rows:
            if eligible > 100_000:
                # 单天删十万行以上会拖垮主从延迟,先报警人工分段删
                alerts.warn("audit_archive",
                            f"待删 {eligible} 行超单次安全阈值,本次跳过",
                            eligible=eligible)
            else:
                # 分批删,一个事务删全量锁表的事不干
                while True:
                    ids = s.execute(
                        select(AuditLogModel.id).where(cond).limit(_DELETE_BATCH)
                    ).scalars().all()
                    if not ids:
                        break
                    s.execute(delete(AuditLogModel).where(AuditLogModel.id.in_(ids)))
                    deleted += len(ids)

    return {"eligible": eligible, "deleted": deleted, "cutoff": cutoff.isoformat()}

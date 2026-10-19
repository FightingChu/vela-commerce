"""死信清扫:统计 outbox 里的 DEAD 行,超阈值报警。

只统计不重放。死信自动重放做过一版,把一条毒丸事件重放了几百次
打挂下游(#VT-2077),从此约定:重放一律走手工脚本,人对着看。

worker 进程内存里的 DeadLetterLog 是另一份(SyncWorker 自建),
两边的口径是:内存版管"本轮",这张表管"全量",对不上是正常的。
"""

from __future__ import annotations

from sqlalchemy import select

from vela.jobs import alerts, context
from vela.jobs.registry import register_job
from vela.messaging.queue_model import OutboxEventModel, OutboxStatus

# 超过这个数说明不是偶发,值班要起来看
_WARN_THRESHOLD = 50


@register_job("dead_letter_sweep", trigger="每 10 分钟")
def run(session=None) -> dict:
    with context.job_session(session) as s:
        stmt = (
            select(OutboxEventModel)
            .where(OutboxEventModel.status == OutboxStatus.DEAD)
            .order_by(OutboxEventModel.id)
        )
        rows = s.execute(stmt).scalars().all()

    dead = len(rows)
    oldest = min((r.created_at for r in rows), default=None)
    if dead >= _WARN_THRESHOLD:
        alerts.error("dead_letter_sweep",
                     f"死信堆积 {dead} 条,超过阈值 {_WARN_THRESHOLD}", dead=dead)
    elif dead:
        alerts.warn("dead_letter_sweep", f"死信 {dead} 条待处理", dead=dead)
    return {
        "dead": dead,
        "oldest": oldest.isoformat() if oldest else None,
        "warn_threshold": _WARN_THRESHOLD,
    }

"""outbox 派发。每分钟一轮,把 due 事件推到进程内总线。

bus 用的是全局默认实例(handler 由各服务启动时 wire),job 进程里
没人订阅时事件也会标记 DISPATCHED——这是有意的:outbox 的语义是
"离开本服务",下游有没有消费不归这层管。

max_batches 兜底防极端积压时单轮跑太久,把下一轮的 cron 顶掉。
真积压了靠告警和手工 flush_pending,别调大这个参数硬扛。
"""

from __future__ import annotations

from vela.jobs import alerts, context
from vela.jobs.registry import register_job
from vela.messaging.bus import get_bus
from vela.messaging.outbox import OutboxRepository
from vela.messaging.worker import SyncWorker

_BATCH_SIZE = 50


@register_job("outbox_dispatch", trigger="每分钟")
def run(session=None, *, max_batches: int = 20) -> dict:
    with context.job_session(session) as s:
        worker = SyncWorker(OutboxRepository(s), get_bus(), batch_size=_BATCH_SIZE)
        total, batches = 0, 0
        while batches < max_batches:
            n = worker.run_once_batch(_BATCH_SIZE)
            if n == 0:
                break
            total += n
            batches += 1

    dead = len(worker.dead_letter)
    if dead:
        alerts.warn("outbox_dispatch", f"本轮 {dead} 条事件进死信", dead=dead)
    if batches == max_batches and total > 0:
        # 打满还没跑空,大概率在积压
        alerts.warn("outbox_dispatch", f"单轮打满 {max_batches} 批仍有积压", dispatched=total)
    return {"dispatched": total, "batches": batches, "dead_letter": dead}

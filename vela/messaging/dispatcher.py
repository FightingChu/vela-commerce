"""一次性清空 outbox 的运维工具。

给手工排障/补数脚本用,别挂到常驻进程里——它会一直跑到
没有 due 事件为止,和 worker 并跑会互相抢活。
"""

from __future__ import annotations

from vela.config.logging import get_logger
from vela.messaging.bus import EventBus
from vela.messaging.outbox import OutboxRepository
from vela.messaging.worker import SyncWorker

log = get_logger(__name__)


def flush_pending(repo: OutboxRepository, bus: EventBus, limit: int | None = None) -> int:
    """把当前 due 的 outbox 事件全部分发掉,返回处理总数。

    失败的事件会按正常重试语义排 next_retry_at,不会被本函数
    反复重试(下次 fetch_due 就不是 due 了)。
    """
    worker = SyncWorker(repo, bus)
    total = 0
    while limit is None or total < limit:
        # limit 要传导到批大小,不然一批就超了
        batch = worker.batch_size if limit is None else min(worker.batch_size, limit - total)
        n = worker.run_once_batch(batch)
        if n == 0:
            break
        total += n
    log.info("outbox_flushed", total=total)
    return total

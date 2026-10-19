"""asyncio 版 worker。和 worker.py 的 SyncWorker 逻辑基本平行,
差异在 gather 并发分发,单条失败不影响同批其他事件。
"""

from __future__ import annotations

import asyncio

from vela.config.clocks import SystemClock
from vela.config.logging import get_logger
from vela.domain.shared.events import make_event
from vela.messaging.bus import EventBus
from vela.messaging.dead_letter import DeadLetterLog
from vela.messaging.outbox import OutboxRepository
from vela.messaging.retry import MAX_ATTEMPTS

log = get_logger(__name__)


class BaseAsyncWorker:
    #: 默认批量与轮询间隔,子类可用类属性直接覆盖
    batch_size = 50
    poll_interval = 5.0

    def __init__(self, outbox_repo: OutboxRepository, bus: EventBus, *,
                 batch_size: int | None = None, clock=None):
        self.outbox_repo = outbox_repo
        self.bus = bus
        self.batch_size = batch_size if batch_size is not None else type(self).batch_size
        self.clock = clock or SystemClock()
        self.dead_letter = DeadLetterLog()

    async def run_once(self) -> int:
        rows = self.outbox_repo.fetch_due(self.clock.now(), limit=self.batch_size)
        if not rows:
            return 0
        await asyncio.gather(*(self._process(row) for row in rows))
        return len(rows)

    async def _process(self, row) -> bool:
        try:
            event = make_event(row.event_type, row.payload, trace=row.trace)
            self.bus.publish(event)
        except Exception as exc:
            log.warning("async_dispatch_failed",
                        event_id=row.id, event_type=row.event_type, error=str(exc))
            row.attempts += 1
            row.last_error = str(exc)[:512]
            if row.attempts > MAX_ATTEMPTS:
                self.outbox_repo.mark_dead(row)
                self.dead_letter.append(
                    {"type": row.event_type, "payload": row.payload, "trace": row.trace,
                     "occurred_at": None},
                    reason=str(exc),
                )
            else:
                self.outbox_repo.mark_retry(row, now=self.clock.now())
            return False
        self.outbox_repo.mark_dispatched(row)
        return True

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await self.run_once()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.poll_interval)
            except asyncio.TimeoutError:
                pass
        log.info("async_worker_stopped", worker=type(self).__name__)


class OrderEventWorker(BaseAsyncWorker):
    # 订单域事件量最大,批拉小一点、轮询密一点(#VT-2201 压测调出来的数)
    batch_size = 10
    poll_interval = 2.0

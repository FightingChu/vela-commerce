"""同步 worker。单进程 job 进程用,asyncio 版看 async_worker。

失败语义:attempts 先 +1,超过 retry.MAX_ATTEMPTS 才进死信。
注意 bus.publish 里 handler 的异常会被吃掉,能走到失败分支的
基本是构造事件或总线本身的错。
"""

from __future__ import annotations

from vela.config.clocks import SystemClock
from vela.config.logging import get_logger
from vela.domain.shared.events import make_event
from vela.messaging.bus import EventBus
from vela.messaging.dead_letter import DeadLetterLog
from vela.messaging.outbox import OutboxRepository
from vela.messaging.retry import MAX_ATTEMPTS

log = get_logger(__name__)


class SyncWorker:

    def __init__(self, outbox_repo: OutboxRepository, bus: EventBus, *,
                 batch_size: int = 50, clock=None):
        self.outbox_repo = outbox_repo
        self.bus = bus
        self.batch_size = batch_size
        self.clock = clock or SystemClock()
        # 死信先内存里放着,#VT-2135 落库后换成 DeadLetterStore
        self.dead_letter = DeadLetterLog()

    def run_once(self) -> int:
        """跑一批,返回本批捞到的事件数(不管成败)。"""
        return self.run_once_batch(self.batch_size)

    def run_once_batch(self, batch_size: int) -> int:
        rows = self.outbox_repo.fetch_due(self.clock.now(), limit=batch_size)
        for row in rows:
            self._process(row)
        return len(rows)

    def _process(self, row) -> bool:
        try:
            event = make_event(row.event_type, row.payload, trace=row.trace)
            self.bus.publish(event)
        except Exception as exc:
            log.warning("outbox_dispatch_failed",
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

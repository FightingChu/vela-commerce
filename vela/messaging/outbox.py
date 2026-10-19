"""outbox 仓储。enqueue 在业务事务里落库,worker 端用 fetch_due 捞。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import or_, select

from vela.config.clocks import utc_now
from vela.db import Repository
from vela.messaging.queue_model import OutboxEventModel, OutboxStatus
from vela.messaging.retry import jitter, next_delay_seconds


class OutboxRepository(Repository[OutboxEventModel]):
    model = OutboxEventModel

    def enqueue(self, etype: str, payload: dict | None, trace: str | None = None) -> OutboxEventModel:
        row = OutboxEventModel(
            event_type=etype,
            payload=dict(payload or {}),
            trace=trace,
        )
        self.session.add(row)
        self.session.flush()  # 先拿 id,调用方好打日志
        return row

    def fetch_due(self, now: dt.datetime | None = None, limit: int = 50) -> list[OutboxEventModel]:
        """PENDING 且重试时间到期(或从未排过重试)的事件。"""
        now = now or utc_now()
        stmt = (
            select(OutboxEventModel)
            .where(
                OutboxEventModel.status == OutboxStatus.PENDING,
                or_(
                    OutboxEventModel.next_retry_at.is_(None),
                    OutboxEventModel.next_retry_at <= now,
                ),
            )
            .order_by(OutboxEventModel.id)
            .limit(limit)
        )
        return list(self.session.execute(self._scoped(stmt)).scalars())

    def mark_dispatched(self, row: OutboxEventModel) -> None:
        row.status = OutboxStatus.DISPATCHED

    def mark_dead(self, row: OutboxEventModel, reason: str | None = None) -> None:
        row.status = OutboxStatus.DEAD
        if reason:
            row.last_error = reason[:512]

    def mark_retry(self, row: OutboxEventModel, reason: str | None = None,
                   now: dt.datetime | None = None) -> None:
        """按 attempts 算指数退避 + 抖动。attempts 由调用方先加好。"""
        delay = next_delay_seconds(row.attempts) + jitter(next_delay_seconds(row.attempts))
        row.next_retry_at = (now or utc_now()) + dt.timedelta(seconds=delay)
        if reason:
            row.last_error = reason[:512]

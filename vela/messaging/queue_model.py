"""outbox 表模型。事务性发件箱,worker 从这里捞事件往总线上分发。"""

from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from vela.db import Base, JsonColumn, PkMixin, TenantColumnMixin, TimestampMixin, UTCDateTime


class OutboxStatus(str, enum.Enum):
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    DEAD = "DEAD"


class OutboxEventModel(Base, PkMixin, TimestampMixin, TenantColumnMixin):
    event_type: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    payload: Mapped[dict] = mapped_column(JsonColumn, default=dict, nullable=False)
    # trace_id,从入口请求透传,没有就空
    trace: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[OutboxStatus] = mapped_column(
        default=OutboxStatus.PENDING, index=True, nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_retry_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, index=True)
    # 最近一次失败原因,截断到 512,排查用
    last_error: Mapped[str | None] = mapped_column(String(512))

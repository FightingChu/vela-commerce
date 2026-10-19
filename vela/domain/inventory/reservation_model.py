"""预占落库模型。"""

from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from vela.db import Base, PkMixin, TenantColumnMixin, TimestampMixin, UTCDateTime


class ReservationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CONSUMED = "CONSUMED"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"


class ReservationModel(Base, PkMixin, TimestampMixin, TenantColumnMixin):
    sku_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    warehouse: Mapped[str] = mapped_column(String(32), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    order_sn: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        default=ReservationStatus.ACTIVE, nullable=False
    )
    ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, index=True, nullable=False)
    released_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    released_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    @property
    def remaining(self) -> int:
        return self.qty - self.released_qty

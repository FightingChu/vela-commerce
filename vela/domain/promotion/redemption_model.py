"""核销流水。一行 = 一张券在一次订单里的实际抵扣。

release(退券)是物理删行——没挂 SoftDeleteMixin,历史口径以
promotion.coupon_released 事件为准,别在这里找"已退"状态。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from vela.db import (
    MONEY_COLUMN,
    Base,
    PkMixin,
    TenantColumnMixin,
    TimestampMixin,
    UTCDateTime,
)


class CouponRedemptionModel(Base, PkMixin, TimestampMixin, TenantColumnMixin):
    coupon_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    order_sn: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    discount_taken = mapped_column(MONEY_COLUMN, nullable=False)
    redeemed_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, nullable=False)

    __table_args__ = (
        # 同单同券同人只允许一行,核销幂等靠它兜底
        UniqueConstraint("coupon_id", "customer_id", "order_sn"),
    )

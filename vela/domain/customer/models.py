"""客户档案与收货地址。

external_id 对接渠道侧(小程序/APP/POS),客户号自己不生成。
客户手机号落库前必须过 phone.mask_phone;收货人电话历史上就是
明文存的,先保持现状,整改随 #VT-2103 一起做。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from vela.config.clocks import utc_now
from vela.db import (
    Base,
    JsonColumn,
    PkMixin,
    SoftDeleteMixin,
    TenantColumnMixin,
    TimestampMixin,
    UTCDateTime,
)


class CustomerModel(Base, PkMixin, TimestampMixin, TenantColumnMixin, SoftDeleteMixin):
    external_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(128), nullable=False)
    # 脱敏后的,形如 138****5678;可空(游客转正式之前的档案)
    phone: Mapped[str | None] = mapped_column(String(32))
    tier: Mapped[str] = mapped_column(String(16), default="V0", nullable=False)
    registered_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime, default=utc_now, nullable=False
    )
    # 营销标签,如 ["高潜", "羊毛党"];结构没人管,消费方自己判空
    tags: Mapped[list | None] = mapped_column(JsonColumn)

    def __repr__(self) -> str:  # pragma: no cover - 排查日志用
        return f"<Customer {self.external_id} tier={self.tier}>"


class AddressModel(Base, PkMixin, TimestampMixin, TenantColumnMixin):
    # 没挂软删:地址一直是物理删,补软删排在 #VT-2210
    customer_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    receiver: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    province: Mapped[str] = mapped_column(String(32), nullable=False)
    city: Mapped[str] = mapped_column(String(32), nullable=False)
    district: Mapped[str | None] = mapped_column(String(32))
    detail: Mapped[str] = mapped_column(String(255), nullable=False)
    # 每客户最多一条默认,靠 service 层 set_default_address 维护,
    # 没建部分唯一索引(老库 sqlite 时代遗留,上了 pg 再补)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

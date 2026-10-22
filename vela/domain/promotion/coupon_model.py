"""券主数据。kind 决定计算规则(见 rules.py),别的字段都是运营填的。

历史上 kind 还有过 GIFT / FREE_SHIPPING,2025Q1 下掉了,
报表里还能查到存量字符串,解析时注意容错。
"""

from __future__ import annotations

import datetime as dt
import enum
from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from vela.db import (
    MONEY_COLUMN,
    Base,
    PkMixin,
    SoftDeleteMixin,
    StrEnumColumn,
    TenantColumnMixin,
    TimestampMixin,
    UTCDateTime,
)


class CouponKind(str, enum.Enum):
    THRESHOLD = "THRESHOLD"        # 满减:amount >= threshold 才生效
    DISCOUNT = "DISCOUNT"          # 折扣:按 rate 乘后再四舍五入
    NO_THRESHOLD = "NO_THRESHOLD"  # 无门槛直减


class CouponModel(Base, PkMixin, TimestampMixin, TenantColumnMixin, SoftDeleteMixin):
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[CouponKind] = mapped_column(
        StrEnumColumn(CouponKind, 32), nullable=False
    )
    # THRESHOLD 用 threshold_amount + discount_amount;
    # DISCOUNT 只用 discount_rate(3 位小数,0.123 = 8.77 折)
    threshold_amount = mapped_column(MONEY_COLUMN, nullable=False)
    discount_amount = mapped_column(MONEY_COLUMN, nullable=False)
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    stackable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    total_quota: Mapped[int] = mapped_column(Integer, nullable=False)
    used_quota: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    per_customer_limit: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    valid_from: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    valid_to: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    @property
    def remaining_quota(self) -> int:
        return self.total_quota - self.used_quota

    def to_rule_row(self) -> dict:
        """给 rules.py 用的裸 dict 视图,纯函数那边不认 ORM 对象。"""
        return {
            "code": self.code,
            "kind": self.kind,
            "threshold_amount": self.threshold_amount,
            "discount_amount": self.discount_amount,
            "discount_rate": self.discount_rate,
            "stackable": self.stackable,
        }

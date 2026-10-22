"""价格册(price book)表模型。查询逻辑见 repository.py,别在 service 里裸 select。

effective_to 为空表示无限期,取价时的比较逻辑注意 NULL 语义。
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from vela.db import (
    MONEY_COLUMN,
    Base,
    PkMixin,
    SoftDeleteMixin,
    TenantColumnMixin,
    TimestampMixin,
    UTCDateTime,
)


class PriceBookEntryModel(Base, PkMixin, TimestampMixin, TenantColumnMixin, SoftDeleteMixin):
    __table_args__ = (
        # 同 sku 同渠道同起效时间只允许一条;改价走 change_price,不插新行
        UniqueConstraint(
            "sku_id", "channel", "effective_from",
            name="uq_price_book_entry_sku_channel_from",
        ),
    )

    sku_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    list_price: Mapped[Decimal] = mapped_column(MONEY_COLUMN, nullable=False)
    # 空表示没有促销价,按 list_price 卖
    sale_price: Mapped[Decimal | None] = mapped_column(MONEY_COLUMN, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    channel: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="")
    effective_from: Mapped[dt.datetime] = mapped_column(UTCDateTime, nullable=False)
    effective_to: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, nullable=True)


class PriceChangeLogModel(Base, PkMixin, TimestampMixin, TenantColumnMixin):
    entry_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    old_price: Mapped[Decimal] = mapped_column(MONEY_COLUMN, nullable=False)
    new_price: Mapped[Decimal] = mapped_column(MONEY_COLUMN, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(64), nullable=False)
    # 空串和 None 都会出现,老数据没强约束
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

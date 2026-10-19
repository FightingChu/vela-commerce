"""库存台账 + 流水。available 是算出来的,不落库——早年落过一列,
两处更新打架出过超卖,见 #VT-1987,后来删了。
"""

from __future__ import annotations

import enum

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from vela.db import Base, PkMixin, TenantColumnMixin, TimestampMixin, VersionMixin


class StockModel(Base, PkMixin, TimestampMixin, TenantColumnMixin, VersionMixin):
    __table_args__ = (UniqueConstraint("sku_id", "warehouse", name="uq_stock_sku_wh"),)

    sku_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    warehouse: Mapped[str] = mapped_column(String(32), nullable=False)
    on_hand: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved


class LedgerDirection(str, enum.Enum):
    IN = "IN"
    OUT = "OUT"


class StockLedgerModel(Base, PkMixin, TimestampMixin, TenantColumnMixin):
    """进出流水。balance_after 存的是 on_hand 变动后的值,对账就靠它。"""

    sku_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    warehouse: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[LedgerDirection] = mapped_column(nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    ref_sn: Mapped[str | None] = mapped_column(String(64), index=True)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)

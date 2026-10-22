"""settlement 域 ORM 模型。

status 存裸 String(枚举 value),读写走 settlement_status property,
和 orders 表同款方案(sa.Enum 的历史坑见 order/models.py 头注释)。
"""

from __future__ import annotations

import datetime as dt
import enum
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vela.config.constants import SETTLEMENT_DEFAULT_TERMS_DAYS
from vela.db import (
    MONEY_COLUMN,
    Base,
    PkMixin,
    SoftDeleteMixin,
    TenantColumnMixin,
    TimestampMixin,
    UTCDateTime,
    VersionMixin,
)
from vela.domain.settlement.states import SettlementStatus
from vela.domain.shared import ZERO

if TYPE_CHECKING:  # pragma: no cover
    pass


class LineKind(str, enum.Enum):
    SALE = "sale"
    REFUND = "refund"


class SettlementModel(
    TenantColumnMixin, SoftDeleteMixin, VersionMixin, TimestampMixin, PkMixin, Base
):
    settlement_sn: Mapped[str] = mapped_column(String(24), nullable=False, unique=True, index=True)
    merchant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    period_start: Mapped[dt.datetime] = mapped_column(UTCDateTime, nullable=False)
    period_end: Mapped[dt.datetime] = mapped_column(UTCDateTime, nullable=False)

    gross_amount: Mapped[Decimal] = mapped_column(MONEY_COLUMN, nullable=False, default=ZERO)
    fee_amount: Mapped[Decimal] = mapped_column(MONEY_COLUMN, nullable=False, default=ZERO)
    net_amount: Mapped[Decimal] = mapped_column(MONEY_COLUMN, nullable=False, default=ZERO)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=SettlementStatus.DRAFT.value
    )

    # 账期天数,建单时从商户费率/账期表快照下来,后期改表不影响已建的单
    terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=SETTLEMENT_DEFAULT_TERMS_DAYS)

    # confirm 时刻单独记一列:due_date = confirmed_at + terms_days,
    # 用 updated_at 凑合的话一次重推就会把账期顶掉(#VT-2148 讨论过)
    confirmed_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, nullable=True)
    pushed_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, nullable=True)
    settled_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, nullable=True)

    # 幂等键 "settlement_push:<token>"。可空:老调用方不带 token 的还不少
    idem_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    lines: Mapped[list[SettlementLineModel]] = relationship(
        order_by="SettlementLineModel.id", cascade="all, delete-orphan"
    )

    @property
    def settlement_status(self) -> SettlementStatus:
        from vela.domain.shared import StateMachine

        return StateMachine.coerce(self.status, SettlementStatus)

    @settlement_status.setter
    def settlement_status(self, value: SettlementStatus) -> None:
        self.status = value.value


class SettlementLineModel(TimestampMixin, PkMixin, Base):
    """结算明细。kind=REFUND 的行 amount 存正数,方向由 kind 表达。"""

    settlement_id: Mapped[int] = mapped_column(
        ForeignKey("settlements.id"), nullable=False, index=True
    )
    order_sn: Mapped[str] = mapped_column(String(24), nullable=False, index=True)

    amount: Mapped[Decimal] = mapped_column(MONEY_COLUMN, nullable=False)
    fee: Mapped[Decimal] = mapped_column(MONEY_COLUMN, nullable=False, default=ZERO)
    kind: Mapped[str] = mapped_column(String(8), nullable=False, default=LineKind.SALE.value)

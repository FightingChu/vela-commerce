"""order 域 ORM 模型。

status 用裸 String(16) 存枚举 value,读写走 order_status property。
早期用过 sa.Enum,pg 上迁移出了不少坑(#VT-1902 删导出事故的间接
原因之一),后来新表一律 String + property。
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vela.db import (
    Base,
    JsonColumn,
    MONEY_COLUMN,
    PkMixin,
    SoftDeleteMixin,
    TenantColumnMixin,
    TimestampMixin,
    UTCDateTime,
    VersionMixin,
)
from vela.domain.order.states import OrderLineStatus, OrderStatus
from vela.domain.shared import ZERO

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.orm import Session


class OrderModel(
    TenantColumnMixin, SoftDeleteMixin, VersionMixin, TimestampMixin, PkMixin, Base
):
    order_sn: Mapped[str] = mapped_column(String(24), nullable=False, unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=OrderStatus.CREATED.value
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")

    total_amount: Mapped[Decimal] = mapped_column(MONEY_COLUMN, nullable=False, default=ZERO)
    discount_amount: Mapped[Decimal] = mapped_column(MONEY_COLUMN, nullable=False, default=ZERO)
    paid_amount: Mapped[Decimal] = mapped_column(MONEY_COLUMN, nullable=False, default=ZERO)
    paid_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, nullable=True)

    channel: Mapped[str] = mapped_column(String(16), nullable=False, default="app")
    # remark 是多用途垃圾桶:幂等标记 / 取消原因 / 拆单溯源都塞这里,
    # 见 order_service.create_order 的注释
    remark: Mapped[str | None] = mapped_column(String(255), nullable=True)

    lines: Mapped[list["OrderLineModel"]] = relationship(
        order_by="OrderLineModel.id", cascade="all, delete-orphan"
    )

    @property
    def order_status(self) -> OrderStatus:
        from vela.domain.shared import StateMachine

        return StateMachine.coerce(self.status, OrderStatus)

    @order_status.setter
    def order_status(self, value: OrderStatus) -> None:
        self.status = value.value


class OrderLineModel(TimestampMixin, PkMixin, Base):
    # 没建数据库级 FK 约束(早期分库迁移嫌它碍事),ORM 层的 relationship
    # 靠这里的 ForeignKey 元数据拼 join
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"), nullable=False, index=True
    )
    sku_id: Mapped[int] = mapped_column(Integer, nullable=False)

    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(MONEY_COLUMN, nullable=False)
    line_amount: Mapped[Decimal] = mapped_column(MONEY_COLUMN, nullable=False)
    # 分摊到行的优惠金额,合计必须严格等于订单 discount_amount
    discount_share: Mapped[Decimal] = mapped_column(MONEY_COLUMN, nullable=False, default=ZERO)

    # 下单时的 sku 快照。老代码只存 sku_id,详情页回查商品表在 #VT-1902
    # 之后补的快照;name 等展示字段由上游 enrichment 填(#VT-2144)
    snapshot: Mapped[dict | None] = mapped_column(JsonColumn, nullable=True)

    line_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=OrderLineStatus.ACTIVE.value
    )


def load_order_lines(session: "Session", order_id: int) -> list[OrderLineModel]:
    """按 id 升序取行。聚合构造时用,保证拆单下标稳定。"""
    from sqlalchemy import select

    stmt = (
        select(OrderLineModel)
        .where(OrderLineModel.order_id == order_id)
        .order_by(OrderLineModel.id)
    )
    return list(session.execute(stmt).scalars())

"""订单仓储。

命名待统一:老代码叫 fetch_x,2025 年重构统一成 get_/list_,这里
fetch_recent 是没清完的(别顺手改,等重构分支,见 db/repository.py 头注释)。
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from sqlalchemy import select

from vela.db import Repository
from vela.domain.order.models import OrderLineModel, OrderModel
from vela.domain.order.order_errors import OrderNotFoundError
from vela.domain.order.states import OrderStatus


class OrderRepository(Repository[OrderModel]):
    model = OrderModel

    def get_by_sn(self, order_sn: str, *, include_deleted: bool = False) -> OrderModel:
        stmt = select(OrderModel).where(OrderModel.order_sn == order_sn)
        obj = self.session.execute(self._scoped(stmt, include_deleted)).scalar_one_or_none()
        if obj is None:
            raise OrderNotFoundError(
                f"订单 {order_sn} 不存在", detail={"order_sn": order_sn}
            )
        return obj

    # 老代码叫 fetch_recent,重构没清完
    def fetch_recent(self, customer_id: int, *, limit: int = 20) -> Sequence[OrderModel]:
        stmt = (
            select(OrderModel)
            .where(OrderModel.customer_id == customer_id)
            .order_by(OrderModel.id.desc())
            .limit(limit)
        )
        return self.session.execute(self._scoped(stmt)).scalars().all()

    def list_waiting_payment(
        self, before: dt.datetime, *, limit: int = 100
    ) -> Sequence[OrderModel]:
        """超时关单 job 用:CREATED 且创建时间早于 before。"""
        stmt = (
            select(OrderModel)
            .where(
                OrderModel.status == OrderStatus.CREATED.value,
                OrderModel.created_at < before,
                OrderModel.paid_at.is_(None),
            )
            .order_by(OrderModel.id)
            .limit(limit)
        )
        return self.session.execute(self._scoped(stmt)).scalars().all()

    def find_by_remark_marker(self, marker: str, *, status: OrderStatus | None = None) -> OrderModel | None:
        """按 remark 里的标记查单。幂等 remark 方案专用,别拿去干别的。

        见 create_order 里的注释:幂等键塞在 remark 里(#VT-2101)。
        """
        stmt = select(OrderModel).where(OrderModel.remark == marker)
        if status is not None:
            stmt = stmt.where(OrderModel.status == status.value)
        return self.session.execute(self._scoped(stmt)).scalar_one_or_none()

    def load_lines(self, order_id: int) -> list[OrderLineModel]:
        stmt = (
            select(OrderLineModel)
            .where(OrderLineModel.order_id == order_id)
            .order_by(OrderLineModel.id)
        )
        return list(self.session.execute(stmt).scalars())

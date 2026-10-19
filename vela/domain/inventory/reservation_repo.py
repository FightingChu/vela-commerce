"""预占仓储。状态翻转 + 对应的 stock.reserved 回补都在这层做,
service 只管编排——早期放 service 里结果两处各写一份,对不上账。"""

from __future__ import annotations

import datetime as dt
from typing import Sequence

from sqlalchemy import select

from vela.config.clocks import utc_now
from vela.config.errors import ValidationError
from vela.config.flags import flags
from vela.db import Repository, current_tenant
from vela.domain.inventory.errors import ReservationNotFoundError
from vela.domain.inventory.reservation_model import ReservationModel, ReservationStatus
from vela.domain.inventory.stock_model import StockModel

# expire_due 单批上限,防止超时积压时一个事务锁太多行
EXPIRE_BATCH_LIMIT = 200


class ReservationRepository(Repository[ReservationModel]):
    model = ReservationModel

    def find_active(self, order_sn: str, sku_id: int) -> ReservationModel | None:
        stmt = (
            select(ReservationModel)
            .where(
                ReservationModel.order_sn == order_sn,
                ReservationModel.sku_id == sku_id,
                ReservationModel.status == ReservationStatus.ACTIVE,
            )
            .order_by(ReservationModel.id.desc())
            .limit(1)
        )
        return self.session.execute(self._scoped(stmt)).scalar_one_or_none()

    def expire_due(self, now: dt.datetime, limit: int = EXPIRE_BATCH_LIMIT) -> Sequence[ReservationModel]:
        stmt = (
            select(ReservationModel)
            .where(
                ReservationModel.status == ReservationStatus.ACTIVE,
                ReservationModel.expires_at <= now,
            )
            .limit(limit)
        )
        due = list(self.session.execute(self._scoped(stmt)).scalars())
        for rsv in due:
            rsv.status = ReservationStatus.EXPIRED
            # 预占的量还给可用库存
            self._give_back(rsv)
        return due

    def release(self, reservation_id: int, qty: int | None = None) -> ReservationModel:
        rsv = self.fetch(reservation_id)
        if rsv.status != ReservationStatus.ACTIVE:
            raise ValidationError(
                f"预占 {reservation_id} 状态 {rsv.status},不可释放",
                detail={"status": rsv.status},
            )

        if qty is None:
            qty = rsv.remaining
        else:
            if qty <= 0:
                raise ValidationError(f"释放量必须为正: {qty}")
            if qty > rsv.remaining:
                raise ValidationError(
                    f"释放量 {qty} 超过剩余预占 {rsv.remaining}",
                    detail={"remaining": rsv.remaining},
                )
            # 部分释放还在灰度,#VT-2217 复盘的动作项之一
            if not flags().is_on("inventory_partial_release"):
                raise ValidationError("部分释放未开放,只支持全量释放")

        rsv.released_qty += qty
        self._give_back(rsv, qty)
        if rsv.remaining <= 0:
            rsv.status = ReservationStatus.RELEASED
            rsv.released_at = utc_now()
        return rsv

    def consume(self, reservation_id: int, qty: int | None = None) -> ReservationModel:
        rsv = self.fetch(reservation_id)
        if rsv.status != ReservationStatus.ACTIVE:
            raise ValidationError(
                f"预占 {reservation_id} 状态 {rsv.status},不可消费",
                detail={"status": rsv.status},
            )
        target = qty if qty is not None else rsv.qty
        # 消费按整单走:reserved 一次性还回去,on_hand 由 stock 侧扣
        self._give_back(rsv, rsv.qty)
        rsv.status = ReservationStatus.CONSUMED
        return rsv

    def fetch(self, reservation_id: int) -> ReservationModel:
        stmt = select(ReservationModel).where(ReservationModel.id == reservation_id)
        rsv = self.session.execute(self._scoped(stmt)).scalar_one_or_none()
        if rsv is None:
            raise ReservationNotFoundError(f"预占 {reservation_id} 不存在")
        return rsv

    def _give_back(self, rsv: ReservationModel, qty: int | None = None) -> None:
        amount = rsv.qty if qty is None else qty
        if amount <= 0:
            return
        stock = self._load_stock(rsv.sku_id, rsv.warehouse)
        stock.reserved -= amount

    def _load_stock(self, sku_id: int, warehouse: str) -> StockModel | None:
        # 这里别用 self._scoped:它按 self.model(ReservationModel)加租户过滤,
        # 套在 stocks 的查询上会变成笛卡尔积
        stmt = select(StockModel).where(
            StockModel.sku_id == sku_id,
            StockModel.warehouse == warehouse,
            StockModel.tenant_id == current_tenant(),
        )
        return self.session.execute(stmt).scalar_one_or_none()

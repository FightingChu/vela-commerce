"""库存仓储。台账余额变动必须走 apply_ledger,别裸改 on_hand——
流水和余额拆开维护是 #VT-1987 的直接教训。
"""

from __future__ import annotations

from sqlalchemy import select

from vela.db import Repository
from vela.domain.inventory.stock_model import LedgerDirection, StockLedgerModel, StockModel


class StockRepository(Repository[StockModel]):
    model = StockModel

    def get_or_create(self, sku_id: int, warehouse: str) -> StockModel:
        stmt = select(StockModel).where(
            StockModel.sku_id == sku_id,
            StockModel.warehouse == warehouse,
        )
        stock = self.session.execute(self._scoped(stmt)).scalar_one_or_none()
        if stock is not None:
            return stock
        stock = StockModel(sku_id=sku_id, warehouse=warehouse, on_hand=0, reserved=0)
        self.session.add(stock)
        self.session.flush()
        return stock

    def apply_ledger(
        self,
        stock: StockModel,
        direction: LedgerDirection,
        qty: int,
        reason: str,
        ref_sn: str | None = None,
    ) -> StockLedgerModel:
        if direction == LedgerDirection.OUT:
            stock.on_hand -= qty
        else:
            stock.on_hand += qty
        entry = StockLedgerModel(
            sku_id=stock.sku_id,
            warehouse=stock.warehouse,
            direction=direction,
            qty=qty,
            reason=reason,
            ref_sn=ref_sn,
            balance_after=stock.on_hand,
        )
        self.session.add(entry)
        return entry

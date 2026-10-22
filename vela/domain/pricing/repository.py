"""价格册仓储。

current_price 的"最低价优先"是业务拍板过的:同一 sku 渠道价允许
多条并行生效(比如平台活动和店铺活动叠着),对外永远报便宜的那条,
争议单据见 #VT-2103。
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import func, or_, select

from vela.config.clocks import utc_now
from vela.db import Repository, not_deleted
from vela.domain.pricing.models import PriceBookEntryModel, PriceChangeLogModel


class PriceBookRepository(Repository[PriceBookEntryModel]):
    model = PriceBookEntryModel

    def current_price(
        self,
        sku_id: int,
        channel: str = "",
        at: dt.datetime | None = None,
    ) -> PriceBookEntryModel | None:
        """取 at 时刻生效的条目,effective_to 为空视为长期有效。没有返回 None。"""
        at = at or utc_now()
        effective_price = func.coalesce(
            PriceBookEntryModel.sale_price, PriceBookEntryModel.list_price
        )
        stmt = self._scoped(not_deleted(PriceBookEntryModel))
        stmt = (
            stmt.where(PriceBookEntryModel.sku_id == sku_id)
            .where(PriceBookEntryModel.channel == channel)
            .where(PriceBookEntryModel.effective_from <= at)
            .where(
                or_(
                    PriceBookEntryModel.effective_to.is_(None),
                    PriceBookEntryModel.effective_to > at,
                )
            )
            .order_by(effective_price.asc(), PriceBookEntryModel.effective_from.desc())
        )
        return self.session.execute(stmt).scalars().first()

    def price_history(self, sku_id: int, channel: str | None = None):
        """sku 的全部条目,含已软删的(历史查询要能看到下架记录)。"""
        stmt = (
            select(PriceBookEntryModel)
            .where(PriceBookEntryModel.sku_id == sku_id)
            .order_by(PriceBookEntryModel.effective_from.asc())
        )
        if channel is not None:
            stmt = stmt.where(PriceBookEntryModel.channel == channel)
        return self.session.execute(stmt).scalars().all()

    def change_price(
        self,
        entry: PriceBookEntryModel,
        new_price: Decimal,
        changed_by: str,
        reason: str = "",
    ) -> PriceBookEntryModel:
        """改 sale_price 并落一条变更日志。old_price 记的是当时的有效价。"""
        old = entry.sale_price if entry.sale_price is not None else entry.list_price
        entry.sale_price = new_price
        self.session.add(
            PriceChangeLogModel(
                entry_id=entry.id,
                old_price=old,
                new_price=new_price,
                changed_by=changed_by,
                reason=reason or None,
            )
        )
        return entry

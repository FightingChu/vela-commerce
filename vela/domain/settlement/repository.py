"""结算单仓储。"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from sqlalchemy import select

from vela.config.errors import NotFoundError
from vela.db import Repository
from vela.domain.settlement.models import SettlementModel
from vela.domain.settlement.states import SettlementStatus


class SettlementRepository(Repository[SettlementModel]):
    model = SettlementModel

    def get_by_sn(self, settlement_sn: str, *, include_deleted: bool = False) -> SettlementModel:
        stmt = select(SettlementModel).where(SettlementModel.settlement_sn == settlement_sn)
        obj = self.session.execute(self._scoped(stmt, include_deleted)).scalar_one_or_none()
        if obj is None:
            raise NotFoundError(
                f"结算单 {settlement_sn} 不存在", detail={"settlement_sn": settlement_sn}
            )
        return obj

    def find_by_period(
        self, merchant_id: int, start: dt.datetime, end: dt.datetime
    ) -> Sequence[SettlementModel]:
        """按商户 + 账期区间查(period 与 [start, end) 有交集即命中)。"""
        stmt = (
            select(SettlementModel)
            .where(
                SettlementModel.merchant_id == merchant_id,
                SettlementModel.period_start < end,
                SettlementModel.period_end >= start,
            )
            .order_by(SettlementModel.id)
        )
        return self.session.execute(self._scoped(stmt)).scalars().all()

    def list_overdue(self, now: dt.datetime, *, limit: int = 100) -> list[SettlementModel]:
        """逾期未结清单。SQL 里先粗筛(period_end < now),账期天数逐单不同,
        精算放 Python:period_end + terms_days < now 才算真逾期。"""
        stmt = (
            select(SettlementModel)
            .where(
                SettlementModel.status.notin_(
                    [SettlementStatus.SETTLED.value, SettlementStatus.FAILED.value]
                ),
                SettlementModel.period_end < now,
            )
            .order_by(SettlementModel.period_end)
            .limit(limit)
        )
        rows = self.session.execute(self._scoped(stmt)).scalars().all()
        overdue = [
            r
            for r in rows
            if r.period_end + dt.timedelta(days=r.terms_days) < now
        ]
        return overdue

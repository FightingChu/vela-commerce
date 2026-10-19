"""结算汇总:某自然月内有交集的结算单,按状态汇总金额。

周期匹配口径是"period 与目标月有交集"(和 repository.find_by_period
一致),不是 period 完全落在月内——跨月账期两边都算,财务认可。
"""

from __future__ import annotations

from sqlalchemy import func

from vela.db import replica_scope
from vela.domain.settlement.models import SettlementModel
from vela.reports.base import scoped_select
from vela.reports.columns import Column, ReportResult
from vela.reports.period import resolve_period
from vela.reports.registry import register_report

_STATUS_ORDER = ("draft", "confirmed", "pushed", "settled", "failed")


@register_report("settlement_summary")
def build(*, month: str) -> ReportResult:
    start, end = resolve_period(month, "month")
    with replica_scope() as session:
        stmt = (
            scoped_select(SettlementModel)
            .with_only_columns(
                SettlementModel.status,
                func.count(SettlementModel.id).label("n"),
                func.sum(SettlementModel.gross_amount).label("gross"),
                func.sum(SettlementModel.fee_amount).label("fee"),
                func.sum(SettlementModel.net_amount).label("net"),
            )
            .where(
                # 与 [start, end) 有交集即命中,口径见模块注释
                SettlementModel.period_start < end,
                SettlementModel.period_end >= start,
            )
            .group_by(SettlementModel.status)
        )
        rows = session.execute(stmt).all()

    buckets = {r[0]: (r[1] or 0, r[2] or 0, r[3] or 0, r[4] or 0) for r in rows}
    out = []
    for status in _STATUS_ORDER:
        n, gross, fee, net = buckets.pop(status, (0, 0, 0, 0))
        out.append(
            {"status": status, "bills": n, "gross": gross, "fee": fee, "net": net}
        )
    for status, (n, gross, fee, net) in sorted(buckets.items()):
        out.append({"status": status, "bills": n, "gross": gross, "fee": fee, "net": net})

    return ReportResult(
        columns=[
            Column("status", "状态"),
            Column("bills", "单据数", "int"),
            Column("gross", "毛额", "money"),
            Column("fee", "佣金", "money"),
            Column("net", "净额", "money"),
        ],
        rows=out,
    )

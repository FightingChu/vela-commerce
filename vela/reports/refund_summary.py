"""退款汇总:按状态笔数/金额,申请时间归期。

金额口径是申请金额(request 时的 amount),不是实际到账——
渠道侧手续费扣减不同步回来,到账口径在对账系统里,别混。
"""

from __future__ import annotations

from sqlalchemy import func

from vela.db import replica_scope

# 退款模型在 returns.py,不在 models.py——历史原因,别"顺手"挪
from vela.domain.order.returns import RefundModel
from vela.reports.base import scoped_select
from vela.reports.columns import Column, ReportResult
from vela.reports.period import resolve_period
from vela.reports.registry import register_report

_STATUS_ORDER = ("pending", "approved", "done", "rejected")


@register_report("refund_summary")
def build(*, period: str, granularity: str = "month") -> ReportResult:
    start, end = resolve_period(period, granularity)
    with replica_scope() as session:
        stmt = (
            scoped_select(RefundModel)
            .with_only_columns(
                RefundModel.status,
                func.count(RefundModel.id).label("n"),
                func.sum(RefundModel.amount).label("amount"),
            )
            .where(RefundModel.applied_at >= start, RefundModel.applied_at < end)
            .group_by(RefundModel.status)
        )
        rows = session.execute(stmt).all()

    counts = {r[0]: (r[1] or 0, r[2] or 0) for r in rows}
    out = []
    for status in _STATUS_ORDER:
        n, amount = counts.pop(status, (0, 0))
        out.append({"status": status, "refunds": n, "amount": amount})
    for status, (n, amount) in sorted(counts.items()):  # 脏状态兜底,同漏斗
        out.append({"status": status, "refunds": n, "amount": amount})

    return ReportResult(
        columns=[
            Column("status", "状态"),
            Column("refunds", "笔数", "int"),
            Column("amount", "申请金额合计", "money"),
        ],
        rows=out,
    )

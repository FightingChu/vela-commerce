"""订单漏斗:一天内各状态单量 + 占比,下单时间口径。

CLOSED(系统关单)和 CANCELLED 分开报,运营口径混了会被财务问
——关单是超时未支付的自动行为,见 states.py 的注释。
"""

from __future__ import annotations

from sqlalchemy import func

from vela.db import replica_scope
from vela.domain.order.models import OrderModel
from vela.reports.base import scoped_select
from vela.reports.columns import Column, ReportResult
from vela.reports.period import resolve_period
from vela.reports.registry import register_report

# 展示顺序即漏斗顺序,DB 里 group by 出来是乱序的
_FUNNEL_ORDER = (
    "created", "paid", "partial_shipped", "shipped", "completed",
    "refunding", "refunded", "cancelled", "closed",
)


@register_report("order_funnel")
def build(*, day: str) -> ReportResult:
    start, end = resolve_period(day, "day")
    with replica_scope() as session:
        stmt = (
            scoped_select(OrderModel)
            .with_only_columns(OrderModel.status, func.count(OrderModel.id).label("n"))
            .where(OrderModel.created_at >= start, OrderModel.created_at < end)
            .group_by(OrderModel.status)
        )
        rows = session.execute(stmt).all()

    counts = {r[0]: r[1] for r in rows}
    total = sum(counts.values())
    out = []
    for status in _FUNNEL_ORDER:
        n = counts.pop(status, 0)
        out.append({"status": status, "orders": n, "share": n / total if total else 0})
    # 未知状态(未来新加的)放最后,别静默丢
    for status, n in sorted(counts.items()):
        out.append({"status": status, "orders": n, "share": n / total if total else 0})

    return ReportResult(
        columns=[
            Column("status", "状态"),
            Column("orders", "订单数", "int"),
            Column("share", "占比", "pct"),
        ],
        rows=out,
    )

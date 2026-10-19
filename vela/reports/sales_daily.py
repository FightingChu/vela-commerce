"""日销售汇总。按支付时间(paid_at)归日——财务口径。

运营曾要求按下单时间,吵了三周的结论是两张报表并存:这张支付
口径给财务,漏斗那张下单口径给运营,别再合并。#VT-2288
"""

from __future__ import annotations

from sqlalchemy import func, select

from vela.db import replica_scope
from vela.domain.order.models import OrderModel
from vela.reports.columns import Column, ReportResult
from vela.reports.period import resolve_period
from vela.reports.registry import register_report


@register_report("sales_daily")
def build(*, day: str) -> ReportResult:
    start, end = resolve_period(day, "day")
    with replica_scope() as session:
        day_expr = func.date(OrderModel.paid_at)
        rows = session.execute(
            select(
                day_expr,
                func.count(OrderModel.id),
                func.sum(OrderModel.paid_amount),
            )
            .where(
                OrderModel.paid_at.is_not(None),
                OrderModel.paid_at >= start,
                OrderModel.paid_at < end,
            )
            .group_by(day_expr)
            .order_by(day_expr)
        ).all()

    out = []
    for d, orders, amount in rows:
        orders = orders or 0
        amount = amount or 0
        out.append(
            {
                "day": str(d),
                "orders": orders,
                "paid_amount": amount,
                # 客单价,0 单时按 0,别除零
                "aov": amount / orders if orders else 0,
            }
        )
    return ReportResult(
        columns=[
            Column("day", "日期"),
            Column("orders", "支付订单数", "int"),
            Column("paid_amount", "支付金额", "money"),
            Column("aov", "客单价", "money"),
        ],
        rows=out,
    )

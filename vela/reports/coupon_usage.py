"""券核销报表:每张券的发放/已用/剩余。

kind 列是原样字符串:历史上还有 GIFT / FREE_SHIPPING 存量,
2025Q1 下架了但数据还在,直接透出,别在报表侧做映射——
运营认识这些老值,映射了反而对不上他们的台账。
"""

from __future__ import annotations

from vela.db import replica_scope
from vela.domain.promotion.coupon_model import CouponModel
from vela.reports.base import scoped_select
from vela.reports.columns import Column, ReportResult
from vela.reports.registry import register_report


@register_report("coupon_usage")
def build(*, include_disabled: bool = True) -> ReportResult:
    with replica_scope() as session:
        stmt = scoped_select(CouponModel).order_by(CouponModel.id)
        if not include_disabled:
            stmt = stmt.where(CouponModel.enabled.is_(True))
        coupons = session.execute(stmt).scalars().all()

    out = []
    for c in coupons:
        total = c.total_quota or 0
        used = c.used_quota or 0
        out.append(
            {
                "code": c.code,
                "title": c.title,
                "kind": str(getattr(c.kind, "value", c.kind)),
                "total": total,
                "used": used,
                "remaining": c.remaining_quota,
                # 核销率,0 发放按 0
                "usage_rate": used / total if total else 0,
            }
        )
    return ReportResult(
        columns=[
            Column("code", "券码"),
            Column("title", "券名称"),
            Column("kind", "类型"),
            Column("total", "发放总量", "int"),
            Column("used", "已核销", "int"),
            Column("remaining", "剩余", "int"),
            Column("usage_rate", "核销率", "pct"),
        ],
        rows=out,
    )

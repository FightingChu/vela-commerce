"""库存快照:跑报表那一刻的全量可用库存。

没有历史版本,要看历史走对账 job 的快照(#VT-2247 落库后再说)。
行数 = sku x 仓库,一般几万行,不截断也行,但统一走
build_report 的 max_export_rows 兜底。
"""

from __future__ import annotations

from vela.db import replica_scope
from vela.domain.inventory.stock_model import StockModel
from vela.reports.base import scoped_select
from vela.reports.columns import Column, ReportResult
from vela.reports.registry import register_report


@register_report("inventory_snapshot")
def build(*, warehouse: str | None = None) -> ReportResult:
    with replica_scope() as session:
        stmt = scoped_select(StockModel)
        if warehouse:
            stmt = stmt.where(StockModel.warehouse == warehouse)
        stmt = stmt.order_by(StockModel.sku_id, StockModel.warehouse)
        stocks = session.execute(stmt).scalars().all()

    out = [
        {
            "sku_id": s.sku_id,
            "warehouse": s.warehouse,
            "on_hand": s.on_hand,
            "reserved": s.reserved,
            # available 是算出来的属性,不落库
            "available": s.available,
        }
        for s in stocks
    ]
    return ReportResult(
        columns=[
            Column("sku_id", "SKU", "int"),
            Column("warehouse", "仓库"),
            Column("on_hand", "在库数量", "int"),
            Column("reserved", "预占数量", "int"),
            Column("available", "可用数量", "int"),
        ],
        rows=out,
    )

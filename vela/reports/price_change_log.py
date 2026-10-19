"""改价流水:最近 N 条价格变更,带 sku/渠道反查。

默认倒序取 500 条——这报表运营拿去看"最近谁在乱调价",
全量导出没意义,要全量走 DBA。limit 上限 5000,再大建议直接
提需求做归档查询。
"""

from __future__ import annotations

from sqlalchemy import select

from vela.db import replica_scope
from vela.domain.pricing.models import PriceBookEntryModel, PriceChangeLogModel
from vela.reports.columns import Column, ReportResult
from vela.reports.registry import register_report

_DEFAULT_LIMIT = 500
_MAX_LIMIT = 5_000


@register_report("price_change_log")
def build(*, sku_id: int | None = None, limit: int = _DEFAULT_LIMIT) -> ReportResult:
    limit = max(1, min(int(limit), _MAX_LIMIT))
    with replica_scope() as session:
        stmt = (
            select(PriceChangeLogModel, PriceBookEntryModel.sku_id, PriceBookEntryModel.channel)
            .join(PriceBookEntryModel, PriceChangeLogModel.entry_id == PriceBookEntryModel.id)
            .order_by(PriceChangeLogModel.id.desc())
            .limit(limit)
        )
        if sku_id is not None:
            stmt = stmt.where(PriceBookEntryModel.sku_id == sku_id)
        rows = session.execute(stmt).all()

    out = []
    for log_row, sku, channel in rows:
        out.append(
            {
                "log_id": log_row.id,
                "sku_id": sku,
                "channel": channel,
                "old_price": log_row.old_price,
                "new_price": log_row.new_price,
                # 涨为正,降为负,运营直接看符号
                "delta": (log_row.new_price or 0) - (log_row.old_price or 0),
                "changed_by": log_row.changed_by,
                "reason": log_row.reason,
                "changed_at": log_row.created_at,
            }
        )
    return ReportResult(
        columns=[
            Column("log_id", "日志ID", "int"),
            Column("sku_id", "SKU", "int"),
            Column("channel", "渠道"),
            Column("old_price", "原价", "money"),
            Column("new_price", "新价", "money"),
            Column("delta", "变动", "money"),
            Column("changed_by", "操作人"),
            Column("reason", "原因"),
            Column("changed_at", "变更时间", "dt"),
        ],
        rows=out,
    )

"""报表包。

入口只有一个:registry.build_report(name, **params),返回
ReportResult。导出走 csv_writer.write_csv。

新报表四件事(和 jobs 的约定对齐):
  1. 建 builder 文件,@register_report("名字") 挂名
  2. builder 返回 ReportResult(columns, rows),rows 的 value 保持
     原始类型(Decimal/datetime),格式化交给导出层
  3. 查询用 replica_scope + base.scoped_select,别裸 select
  4. 本文件末尾加 import(注册靠副作用,同 #VT-2153 的教训)
"""

from vela.reports.columns import Column, ReportResult
from vela.reports.csv_writer import clip_cell, write_csv
from vela.reports.period import parse_granularity, resolve_period
from vela.reports.registry import build_report, get_builder, list_reports, register_report

# ---- 全量挂载 builder(注册靠 import 副作用) ----
from vela.reports import (  # noqa: F401
    coupon_usage,
    customer_cohorts,
    inventory_snapshot,
    order_funnel,
    price_change_log,
    refund_summary,
    sales_daily,
    settlement_summary,
)

__all__ = [
    "Column",
    "ReportResult",
    "clip_cell",
    "write_csv",
    "parse_granularity",
    "resolve_period",
    "build_report",
    "get_builder",
    "list_reports",
    "register_report",
]

"""客户月度注册队列:按注册月分桶计数。

Python 分桶不走 SQL 的 date_trunc/strftime——两个库函数名都对
不上,报表要同时在 sqlite(测试)和 pg(线上)跑,别引入方言。
客户表几十万行,内存分桶没压力,实测 200ms 以内。
"""

from __future__ import annotations

from sqlalchemy import select

from vela.db import batch_iter, replica_scope
from vela.domain.customer.models import CustomerModel
from vela.reports.base import scoped_select
from vela.reports.columns import Column, ReportResult
from vela.reports.registry import register_report


@register_report("customer_cohorts")
def build(*, batch_rows: int | None = None) -> ReportResult:
    buckets: dict[str, int] = {}
    with replica_scope() as session:
        stmt = scoped_select(CustomerModel)
        # 游标分批,和 tier_recalculate 同款做法;pk_attr 显式给 id,
        # batch_iter 默认拿 columns[0](那是 external_id)
        for cust in batch_iter(session, stmt, batch_rows=batch_rows, pk_attr=CustomerModel.id):
            registered = cust.registered_at
            if registered is None:  # 老数据有空的,归到 "未知"
                key = "未知"
            else:
                key = f"{registered.year:04d}-{registered.month:02d}"
            buckets[key] = buckets.get(key, 0) + 1

    rows = [
        {"month": k, "new_customers": v}
        for k, v in sorted(buckets.items(), key=lambda kv: (kv[0] != "未知", kv[0]))
    ]
    return ReportResult(
        columns=[
            Column("month", "注册月份"),
            Column("new_customers", "新增客户数", "int"),
        ],
        rows=rows,
    )

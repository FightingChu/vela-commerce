"""会员等级重算。每周一凌晨跑一轮。

现状只做"校准":tier 字段历史上被 CRM 接口写过脏值(空串、
V9、"vip" 各种都有),这里把非法值归回 V0 并出分布统计,给运营
的等级周报用。消费额定级在订单宽表(#VT-2308)侧实现;定级规则
变更是否回溯历史等级,以法务 2026-08 的书面结论为准。
"""

from __future__ import annotations

from sqlalchemy import select

from vela.db import batch_iter
from vela.domain.customer.models import CustomerModel
from vela.domain.customer.tier import Tier
from vela.jobs import context
from vela.jobs.registry import register_job


@register_job("tier_recalculate", trigger="每周一 04:30")
def run(session=None, *, batch_rows: int | None = None) -> dict:
    valid = {t.value for t in Tier}
    by_tier: dict[str, int] = {}
    total, fixed = 0, 0

    with context.job_session(session) as s:
        stmt = select(CustomerModel)
        # 客户表几十万行,按主键分批游,一把梭会把 32M 老实例打爆。
        # pk_attr 必须显式给 id:batch_iter 默认取 stmt.columns[0],
        # 那是 external_id,不是主键
        for cust in batch_iter(s, stmt, batch_rows=batch_rows, pk_attr=CustomerModel.id):
            total += 1
            if cust.tier not in valid:
                cust.tier = Tier.V0.value
                fixed += 1
                by_tier[Tier.V0.value] = by_tier.get(Tier.V0.value, 0) + 1
            else:
                by_tier[cust.tier] = by_tier.get(cust.tier, 0) + 1

    return {"customers": total, "fixed": fixed, "by_tier": by_tier}

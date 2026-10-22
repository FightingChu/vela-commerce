"""客群圈选,纯函数。

营销 job 和离线报表共用,所以不碰 session,输入输出都是内存对象
——想在离线表上批量跑的诉求见 #VT-2031,别偷偷加数据库参数。
"""

from __future__ import annotations

import datetime as dt
import decimal
from collections.abc import Iterable

from vela.config.clocks import utc_now
from vela.domain.customer.tier import Tier, TierLike, as_tier


def segment_by_tier(customers: Iterable, tier: TierLike) -> list:
    """按等级过滤。元素带 .tier 属性即可(CustomerModel 或离线行对象)。"""
    want = as_tier(tier)
    return [c for c in customers if c.tier == want]


def segment_by_recency(
    orders_stats: list[dict],
    days: int = 90,
    *,
    now: dt.datetime | None = None,
) -> list[int]:
    """最近 N 天无单的客户 id 列表。

    orders_stats 每行 {"customer_id": int, "last_order_at": datetime|None}。
    last_order_at 为 None 视为从未下单,直接归入沉睡。裸 datetime 按
    UTC 解释(全库约定)。注意:全集以外(从未出现在统计里的客户)
    这里看不到,营销侧要合并客户主档再发券。
    """
    ref = now or utc_now()
    cutoff = ref - dt.timedelta(days=days)
    stale: list[int] = []
    for row in orders_stats:
        last = row.get("last_order_at")
        if last is not None:
            if last.tzinfo is None:
                last = last.replace(tzinfo=dt.timezone.utc)
            if last >= cutoff:
                continue
        stale.append(row["customer_id"])
    return stale


def rfm_tier(r: float, f: int, m: decimal.Decimal | float | str) -> str:
    """简化 RFM 打分,返回 高/中/低。

    r=距上次下单天数(越小越好),f=下单次数,m=累计金额。
    阈值是 2025-03 拉全量分位数定的,改动先问运营。
    """
    amount = decimal.Decimal(str(m))
    r_score = 3 if r <= 30 else 2 if r <= 90 else 1
    f_score = 3 if f >= 10 else 2 if f >= 3 else 1
    m_score = 3 if amount >= 5000 else 2 if amount >= 1000 else 1
    total = r_score + f_score + m_score
    if total >= 8:
        return "高"
    if total >= 5:
        return "中"
    return "低"


# Tier 顺手 re-export,消费方少写一个 import
__all__ = ["Tier", "rfm_tier", "segment_by_recency", "segment_by_tier"]

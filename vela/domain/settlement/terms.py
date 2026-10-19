"""账期与费率。

账期从 confirm 时刻起算(due_date = confirmed_at + terms_days),
不是从 period_end 起算——财务侧 2025Q3 定的口径,别改。
商户费率表目前是调用方传进来的 dict,商户主数据服务化之后这里
换注入,见 #VT-2196。
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from vela.config.constants import SETTLEMENT_DEFAULT_TERMS_DAYS

# 默认平台费率。商户表里没配的都按这个收,历史口径,动之前找财务对
DEFAULT_FEE_RATE = Decimal("0.006")


def due_date(confirmed_at: dt.datetime, terms_days: int | None = None) -> dt.datetime:
    """到期日 = 确认时刻 + 账期天数。terms_days 缺省走平台默认。"""
    days = terms_days if terms_days is not None else SETTLEMENT_DEFAULT_TERMS_DAYS
    if days < 0:
        raise ValueError(f"账期天数不能为负: {days}")
    return confirmed_at + dt.timedelta(days=days)


def effective_terms(merchant_id: int, table: dict) -> dict:
    """从商户费率/账期表取生效配置,缺商户给平台默认。

    table 形如 {merchant_id: {"terms_days": n, "fee_rate": Decimal}}。
    返回浅拷贝,调用方改返回值不影响表。
    """
    entry = table.get(merchant_id) if table else None
    if not entry:
        return {
            "terms_days": SETTLEMENT_DEFAULT_TERMS_DAYS,
            "fee_rate": DEFAULT_FEE_RATE,
        }
    merged = {
        "terms_days": entry.get("terms_days", SETTLEMENT_DEFAULT_TERMS_DAYS),
        "fee_rate": entry.get("fee_rate", DEFAULT_FEE_RATE),
    }
    if not isinstance(merged["fee_rate"], Decimal):
        # str/int 都收,float 拒掉(to_decimal 的规矩)
        from vela.domain.shared import to_decimal

        merged["fee_rate"] = to_decimal(merged["fee_rate"])
    return merged


def _as_aware(at: dt.datetime) -> dt.datetime:
    # sqlite 存裸 datetime,一律按 UTC 解释(见 clocks.py 的口径)
    if at.tzinfo is None:
        return at.replace(tzinfo=dt.timezone.utc)
    return at


def is_overdue(settlement_row: dict, now: dt.datetime) -> bool:
    """逾期判定:未结清 且 到期日已过。

    settlement_row 是 dict(报表侧从宽表喂进来,不走 ORM),
    需要的键:status、due_date;没有 due_date 时用 confirmed_at + terms_days 算。
    """
    status = str(settlement_row.get("status", "")).upper()
    if status == "SETTLED":
        return False
    due = settlement_row.get("due_date")
    if due is None:
        confirmed = settlement_row.get("confirmed_at")
        if confirmed is None:
            return False
        due = due_date(confirmed, settlement_row.get("terms_days"))
    return _as_aware(due) < _as_aware(now)

"""结算查询/逾期管理。读侧为主,给财务后台用。

"真逾期"的口径:period_end + terms_days < now,粗筛在 SQL、精算在
Python(repository.list_overdue 注释解释了为什么),这里原样透出。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from vela.config.clocks import utc_now
from vela.domain.settlement import SettlementRepository
from vela.service.converters import dt_to_iso, money


def settlement_view(session: Session, settlement_sn: str) -> dict | None:
    """结算单视图。含行明细,行金额也转 str(财务侧对账直接贴表)。"""
    try:
        model = SettlementRepository(session).get_by_sn(settlement_sn)
    except Exception:
        # get_by_sn 抛 NotFoundError;查询接口统一 None 语义
        return None
    return {
        "settlement_sn": model.settlement_sn,
        "merchant_id": model.merchant_id,
        "status": model.status,
        "gross": money(model.gross_amount),
        "fee": money(model.fee_amount),
        "net": money(model.net_amount),
        "terms_days": model.terms_days,
        "period_start": dt_to_iso(model.period_start),
        "period_end": dt_to_iso(model.period_end),
        "lines": [
            {
                "order_sn": line.order_sn,
                "amount": money(line.amount),
                "fee": money(line.fee),
                "kind": line.kind,
            }
            for line in model.lines
        ],
    }


def list_overdue(
    session: Session,
    now: dt.datetime | None = None,
    *,
    limit: int = 100,
) -> list[dict]:
    """逾期未结清单,账期最早的排前面(催收顺序)。"""
    rows = SettlementRepository(session).list_overdue(now or utc_now(), limit=limit)
    return [
        {
            "settlement_sn": r.settlement_sn,
            "merchant_id": r.merchant_id,
            "net": money(r.net_amount),
            "period_end": dt_to_iso(r.period_end),
            "terms_days": r.terms_days,
        }
        for r in rows
    ]


def find_by_period(
    session: Session,
    merchant_id: int,
    start: dt.datetime,
    end: dt.datetime,
) -> list[dict]:
    """按账期区间查商户结算单(period 与 [start, end) 有交集即命中)。"""
    rows = SettlementRepository(session).find_by_period(merchant_id, start, end)
    return [
        {
            "settlement_sn": r.settlement_sn,
            "status": r.status,
            "net": money(r.net_amount),
            "period_start": dt_to_iso(r.period_start),
            "period_end": dt_to_iso(r.period_end),
        }
        for r in rows
    ]

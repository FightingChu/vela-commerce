"""结算域事件类型。type 约定 settlement.<动作>,和 order 域同款。

事件只带 sn 和关键金额,明细让消费方回查——历史上曾把整张对账单
塞进 payload,消息队列直接被打爆过(#VT-1956)。
"""

from __future__ import annotations

from vela.domain.shared import make_event

EVENT_SETTLEMENT_PUSHED = "settlement.pushed"
EVENT_SETTLEMENT_SETTLED = "settlement.settled"
EVENT_SETTLEMENT_RECONCILED = "settlement.reconciled"


def make_settlement_event(etype: str, sn: str, extra: dict | None = None) -> dict:
    """结算单事件统一入口。sn 是结算单号。"""
    payload = {"settlement_sn": sn}
    if extra:
        payload.update(extra)
    return make_event(etype, payload)

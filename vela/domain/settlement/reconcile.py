"""对账差异比对。ours 是我方口径,theirs 是渠道/清分侧口径。

delta 约定 = expected - actual(我方 - 渠道),正数表示我方多记。
"""

from __future__ import annotations

from decimal import Decimal

from vela.domain.shared import ZERO, make_event, to_decimal
from vela.domain.settlement.events import EVENT_SETTLEMENT_RECONCILED


def diff_statements(ours: dict, theirs: dict) -> list[dict]:
    """ours/theirs 都是 {order_sn: Decimal},返回差异行列表。

    单边缺失按 0 参与比较(对方漏单/我方漏单都能暴露出来)。
    """
    ours = ours or {}
    theirs = theirs or {}
    sn_set = set(ours) | set(theirs)

    diff: list[dict] = []
    for sn in sorted(sn_set, key=str):
        expected = to_decimal(ours.get(sn, ZERO))
        actual = to_decimal(theirs.get(sn, ZERO))
        delta = expected - actual
        if delta != ZERO:
            diff.append(
                {"order_sn": sn, "expected": expected, "actual": actual, "delta": delta}
            )
    return diff


def emit_reconciled(diff: list[dict], period: str) -> dict | None:
    """有差异才发 reconciliation 事件,无差异返回 None(别发空事件,噪音)。"""
    if not diff:
        return None
    return make_event(
        EVENT_SETTLEMENT_RECONCILED,
        {
            "period": period,
            "diff_count": len(diff),
            "order_sns": [row["order_sn"] for row in diff],
        },
    )

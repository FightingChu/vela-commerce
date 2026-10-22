"""对账单汇总。

费用口径:逐行 round_half_up 后再合计,不先合金额再算费——
两种算法能差出一分钱,渠道侧按逐行收,我们对齐它(#VT-2003)。
REFUND 行的费用是负数(按费率退),所以 fee 合计 = 各行 fee 直接加。
"""

from __future__ import annotations

from vela.config.errors import ValidationError
from vela.config.logging import get_logger
from vela.domain.shared import (
    UNAVAILABLE,
    ZERO,
    EventBatch,
    payload_of,
    round_half_up,
    to_decimal,
)

log = get_logger(__name__)

SALE = "SALE"
REFUND = "REFUND"

_KINDS = (SALE, REFUND)


def build_statement(orders: list[dict], *, fee_rate) -> dict:
    """orders 每行:{"order_sn": str, "amount": Decimal, "kind": "SALE"/"REFUND"}。

    返回 {"gross", "refund_total", "fee", "net", "lines"},lines 每行带
    逐行费用(REFUND 行 fee 为负)。
    """
    rate = to_decimal(fee_rate)
    if rate < ZERO:
        raise ValidationError(f"费率不能为负: {rate}")

    gross = ZERO
    refund_total = ZERO
    fee = ZERO
    lines: list[dict] = []

    for row in orders or []:
        sn = row.get("order_sn")
        if not sn:
            raise ValidationError(f"对账行缺 order_sn: {row!r}")
        kind = str(row.get("kind", SALE)).upper()
        if kind not in _KINDS:
            raise ValidationError(f"未知对账行类型: {kind!r}(order_sn={sn})")
        amount = to_decimal(row["amount"])

        # REFUND 的 fee 记负数,方向由 kind 表达,和明细行同款口径
        fee_line = round_half_up(amount * rate)
        if kind == REFUND:
            fee_line = -fee_line
            refund_total += amount
        else:
            gross += amount
        fee += fee_line

        lines.append(
            {"order_sn": sn, "amount": amount, "kind": kind, "fee": fee_line}
        )

    net = gross - refund_total - fee
    return {
        "gross": gross,
        "refund_total": refund_total,
        "fee": fee,
        "net": net,
        "lines": lines,
    }


def orders_from_batches(
    batches: list[EventBatch], etype: str = "order.paid"
) -> list[dict]:
    """从事件批次的 payload 组装对账行。凑不齐就返回空列表。

    空/不可用两态([] 输入或 merge_all 返回 UNAVAILABLE)都归 [] ,
    由 log 区分——报表 job 不需要区分这两种,但对账侧要看日志排障。
    """
    merged = EventBatch.merge_all(batches)
    if not batches:
        log.info("statement_batches_empty", etype=etype)
        return []
    if merged == UNAVAILABLE:
        log.info("statement_batches_unavailable", etype=etype)
        return []

    rows: list[dict] = []
    for batch in batches:
        for event in batch.by_type(etype):
            sn = payload_of(event, "order_sn")
            amount = payload_of(event, "amount")
            if sn is None or amount is None:
                # 老事件可能缺字段,跳过并留痕,别让单条脏数据炸整个 job
                log.info("statement_skip_bad_event", etype=etype, order_sn=sn)
                continue
            rows.append(
                {
                    "order_sn": sn,
                    "amount": to_decimal(amount),
                    "kind": str(payload_of(event, "kind", SALE)).upper(),
                }
            )
    return rows

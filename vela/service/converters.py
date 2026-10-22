"""service 层公共转换器。model -> 对外 dict 的唯一出口。

对外金额一律 str(2 位小数),时间一律 ISO8601——api 并行任务就按
这里的形状对契约,别在各自模块里手搓格式化(2026-02 出过两侧
小数位不一致的对账差异)。
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from vela.domain.shared import round_half_up, to_decimal


def money(value) -> str:
    """金额 -> 对外字符串。None 按 0 处理(老数据 paid_amount 有 NULL)。"""
    if value is None:
        value = Decimal(0)
    return str(round_half_up(to_decimal(value)))


def dt_to_iso(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    # 裸 datetime 按 UTC 解释,和 clocks.to_local 的口径一致
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.isoformat()


def reservation_ref_of(line) -> int | None:
    """从行快照里抠预占凭证。没有就 None,别猜。"""
    snapshot = line.snapshot or {}
    ref = snapshot.get("reservation_ref")
    return int(ref) if ref is not None else None


def line_to_view(line) -> dict:
    return {
        "sku_id": line.sku_id,
        "qty": line.qty,
        "unit_price": money(line.unit_price),
        "line_amount": money(line.line_amount),
        "discount_share": money(line.discount_share),
        "reservation_ref": reservation_ref_of(line),
    }


def order_to_view(model, lines=None) -> dict:
    """订单 -> 对外视图。lines 不传就从 relationship 拉。"""
    if lines is None:
        lines = list(model.lines)
    return {
        "order_sn": model.order_sn,
        "customer_id": model.customer_id,
        "status": model.status,
        "channel": model.channel,
        "total": money(model.total_amount),
        "discount": money(model.discount_amount),
        "paid": money(model.paid_amount),
        "created_at": dt_to_iso(model.created_at),
        "lines": [line_to_view(line) for line in lines],
    }


def model_to_dict(obj: Any, fields: list[str]) -> dict:
    """按字段白名单抽数,顺手做 money/datetime 的格式化。宽泛兜底,
    特殊视图请写专门的 to_view,别都挤到这里。"""
    out: dict = {}
    for name in fields:
        value = getattr(obj, name, None)
        if isinstance(value, Decimal):
            out[name] = money(value)
        elif isinstance(value, dt.datetime):
            out[name] = dt_to_iso(value)
        else:
            out[name] = value
    return out

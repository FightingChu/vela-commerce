"""促销域事件类型。

改名等于事故,只能加新的(参照 inventory/events.py 的约定,
#VT-2217 之后统一收敛到这份清单)。make_* 帮助函数把 payload
字段约定固化住,别处手拼 dict 容易漏字段。
"""

from __future__ import annotations

from vela.domain.shared import make_event

EVENT_COUPON_REDEEMED = "promotion.coupon_redeemed"
EVENT_COUPON_RELEASED = "promotion.coupon_released"

__all__ = [
    "EVENT_COUPON_REDEEMED",
    "EVENT_COUPON_RELEASED",
    "make_coupon_redeemed",
    "make_coupon_released",
]


def make_coupon_redeemed(
    *,
    coupon_code: str,
    customer_id: str,
    order_sn: str,
    discount_taken,
    trace: str | None = None,
) -> dict:
    return make_event(
        EVENT_COUPON_REDEEMED,
        {
            "coupon_code": coupon_code,
            "customer_id": customer_id,
            "order_sn": order_sn,
            # 事件里过 JSON 序列化,Decimal 转字符串由信封层做
            "discount_taken": str(discount_taken),
        },
        trace=trace or order_sn,
    )


def make_coupon_released(
    *,
    coupon_code: str,
    customer_id: str,
    order_sn: str,
    discount_returned,
    trace: str | None = None,
) -> dict:
    return make_event(
        EVENT_COUPON_RELEASED,
        {
            "coupon_code": coupon_code,
            "customer_id": customer_id,
            "order_sn": order_sn,
            "discount_returned": str(discount_returned),
        },
        trace=trace or order_sn,
    )

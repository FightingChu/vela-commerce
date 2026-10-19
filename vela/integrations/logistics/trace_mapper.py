# -*- coding: utf-8 -*-
"""物流轨迹状态映射。

各物流商的状态码五花八门,在这里收敛成内部标准状态。
映射表是按渠道文档 + 半年轨迹抽样对出来的,新增状态先加 UNKNOWN
兜底观察一周,确认语义再映射,别想当然。
"""

from __future__ import annotations

from vela.config.logging import get_logger

log = get_logger(__name__)

# 内部标准状态。对外 API 只透出这六个,新增要过 product 评审
TRACE_PICKED_UP = "picked_up"
TRACE_IN_TRANSIT = "in_transit"
TRACE_ARRIVED_CITY = "arrived_city"
TRACE_OUT_FOR_DELIVERY = "out_for_delivery"
TRACE_DELIVERED = "delivered"
TRACE_EXCEPTION = "exception"
TRACE_UNKNOWN = "unknown"

# 顺丰。raw code 是他们文档里的 opCode
_SF_MAP = {
    "50": TRACE_PICKED_UP,
    "30": TRACE_IN_TRANSIT,
    "31": TRACE_IN_TRANSIT,
    "36": TRACE_ARRIVED_CITY,
    "44": TRACE_OUT_FOR_DELIVERY,
    "80": TRACE_DELIVERED,
    "8000": TRACE_DELIVERED,
    "99": TRACE_EXCEPTION,
}

# 中通 / 圆通用的是文本描述,按关键字匹配(文档不给状态码,只能这么干)
_TEXT_RULES: tuple[tuple[str, str], ...] = (
    ("已签收", TRACE_DELIVERED),
    ("签收", TRACE_DELIVERED),
    ("派送", TRACE_OUT_FOR_DELIVERY),
    ("到达", TRACE_ARRIVED_CITY),
    ("装车", TRACE_IN_TRANSIT),
    ("运输中", TRACE_IN_TRANSIT),
    ("已揽收", TRACE_PICKED_UP),
    ("揽件", TRACE_PICKED_UP),
    ("异常", TRACE_EXCEPTION),
    ("退回", TRACE_EXCEPTION),
)

_TEXT_MAPS = {"yto": _TEXT_RULES, "zto": _TEXT_RULES}


def map_status(carrier: str, raw_status: str, desc: str = "") -> str:
    """渠道原始状态 -> 内部标准状态。认不出返回 unknown,不抛。"""
    carrier = (carrier or "").lower()
    if carrier == "sf":
        mapped = _SF_MAP.get(str(raw_status).strip())
        if mapped:
            return mapped
    rules = _TEXT_MAPS.get(carrier)
    if rules:
        text = f"{raw_status}{desc}"
        for keyword, status in rules:
            if keyword in text:
                return status
    if raw_status or desc:
        # 每天限量打,防止渠道改版刷屏
        log.warning(
            "trace_status_unmapped", carrier=carrier,
            raw=str(raw_status)[:32], rate_limited=True,
        )
    return TRACE_UNKNOWN

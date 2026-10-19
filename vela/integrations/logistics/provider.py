# -*- coding: utf-8 -*-
"""物流商适配器协议与数据结构。

轨迹点内部状态用 trace_mapper 里的常量,本文件只透传原始值。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class WaybillRequest:
    order_no: str
    carrier: str                     # sf / yto / zto / ems
    sender: dict                     # {name, phone, province, city, address}
    receiver: dict
    parcel: dict | None = None       # {weight_kg, length_cm, ...},可缺省

    def __post_init__(self):
        if not self.order_no:
            raise ValueError("order_no 不能为空")
        if self.carrier not in _SUPPORTED_CARRIERS:
            raise ValueError(f"不支持的承运商: {self.carrier}")


# 2024 年下线了天天/百世,别再加回来,历史单走只读归档
_SUPPORTED_CARRIERS = ("sf", "yto", "zto", "ems")


@dataclass
class WaybillResult:
    waybill_no: str
    carrier: str
    label_url: str = ""              # 面单 PDF 地址,渠道给的,有时效
    raw: dict = field(default_factory=dict)


@dataclass
class TracePoint:
    time: datetime
    status: str                      # 内部标准化状态,见 trace_mapper
    desc: str = ""                   # 渠道原文,给用户看的话保留原文
    raw_status: str = ""


@dataclass
class CancelResult:
    ok: bool
    reason: str = ""


class LogisticsProvider(Protocol):
    """每家物流商一个实现。别做"通用适配器",各家中报文差异大到没意义。"""

    def create_waybill(self, req: WaybillRequest) -> WaybillResult:
        """下单取号。渠道超时后必须 query 单号,不能直接重下(会重复取号)。"""
        ...

    def query_trace(self, waybill_no: str) -> list[TracePoint]:
        """查轨迹,按时间升序返回。"""
        ...

    def cancel(self, waybill_no: str, reason: str = "") -> CancelResult:
        """取消取号。已揽收的单渠道会拒绝,ok=False 带 reason。"""
        ...

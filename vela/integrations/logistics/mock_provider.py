"""内存模拟物流商。联调/单测用。轨迹是假的但结构是真的。"""

from __future__ import annotations

import itertools
from datetime import datetime, timedelta, timezone

from vela.integrations.logistics.provider import (
    CancelResult,
    TracePoint,
    WaybillRequest,
    WaybillResult,
)
from vela.integrations.logistics.trace_mapper import (
    TRACE_DELIVERED,
    TRACE_IN_TRANSIT,
    TRACE_PICKED_UP,
)


class MockLogisticsProvider:
    """实现 LogisticsProvider 协议。settle_trace 可以手动推轨迹。"""

    def __init__(self):
        self._seq = itertools.count(88001)
        self._waybills: dict[str, list[TracePoint]] = {}
        self.cancelled: set[str] = set()

    def create_waybill(self, req: WaybillRequest) -> WaybillResult:
        no = f"MOCK{next(self._seq)}{req.carrier.upper()}"
        self._waybills[no] = [self._point(TRACE_PICKED_UP, "已揽收(模拟)")]
        return WaybillResult(
            waybill_no=no,
            carrier=req.carrier,
            label_url=f"memory://labels/{no}.pdf",
            raw={"mock": True},
        )

    def query_trace(self, waybill_no: str) -> list[TracePoint]:
        return list(self._waybills.get(waybill_no.upper(), []))

    def cancel(self, waybill_no: str, reason: str = "") -> CancelResult:
        no = waybill_no.upper()
        if no not in self._waybills:
            return CancelResult(ok=False, reason="单号不存在")
        traces = self._waybills[no]
        # 已到 in_transit 之后渠道就拒了,模拟这个行为
        if any(t.status != TRACE_PICKED_UP for t in traces):
            return CancelResult(ok=False, reason="已揽收在途,拒绝取消")
        self.cancelled.add(no)
        return CancelResult(ok=True, reason=reason)

    # -- 测试辅助 ---------------------------------------------------------

    def advance(self, waybill_no: str, stage: str = TRACE_IN_TRANSIT) -> None:
        self._waybills[waybill_no.upper()].append(self._point(stage, f"模拟推进: {stage}"))

    def finish(self, waybill_no: str) -> None:
        self.advance(waybill_no, TRACE_DELIVERED)

    @staticmethod
    def _point(status: str, desc: str) -> TracePoint:
        return TracePoint(
            time=datetime.now(timezone.utc) - timedelta(minutes=0),
            status=status,
            desc=desc,
        )

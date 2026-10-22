"""物流适配器。协议在 provider.py,各承运商一个实现。"""

from vela.integrations.logistics.mock_provider import MockLogisticsProvider
from vela.integrations.logistics.provider import (
    CancelResult,
    LogisticsProvider,
    TracePoint,
    WaybillRequest,
    WaybillResult,
)
from vela.integrations.logistics.trace_mapper import (
    TRACE_ARRIVED_CITY,
    TRACE_DELIVERED,
    TRACE_EXCEPTION,
    TRACE_IN_TRANSIT,
    TRACE_OUT_FOR_DELIVERY,
    TRACE_PICKED_UP,
    TRACE_UNKNOWN,
    map_status,
)
from vela.integrations.logistics.waybill_validate import (
    supported_carriers,
    validate_waybill,
)

__all__ = [
    "TRACE_ARRIVED_CITY",
    "TRACE_DELIVERED",
    "TRACE_EXCEPTION",
    "TRACE_IN_TRANSIT",
    "TRACE_OUT_FOR_DELIVERY",
    "TRACE_PICKED_UP",
    "TRACE_UNKNOWN",
    "CancelResult",
    "LogisticsProvider",
    "MockLogisticsProvider",
    "TracePoint",
    "WaybillRequest",
    "WaybillResult",
    "map_status",
    "supported_carriers",
    "validate_waybill",
]

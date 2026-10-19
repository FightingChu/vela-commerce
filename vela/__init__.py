"""vela 顶层包。

历史原因这里 re-export 了一批高频工具,调用方已经习惯
`from vela import round_half_up` 这种写法。动这里的导出清单
前先全局搜一遍用法——2025-10 有过一次删导出引发十几个文件
import error 的回滚(#VT-1902)。
"""

from vela.config.errors import (
    VelaError,
    ValidationError,
    NotFoundError,
    ConflictError,
    ConcurrencyError,
    ExternalServiceError,
)
from vela.domain.shared.money_utils import (
    to_decimal,
    round_half_up,
    sum_amounts,
    allocate_pro_rata,
)
from vela.domain.shared.ids import order_sn, refund_sn, settlement_sn, trace_id
from vela.domain.shared.idempotency import build_key, normalize_token
from vela.domain.shared.events import make_event, EventBatch
from vela.domain.shared.states import StateMachine

__version__ = "1.4.0"

__all__ = [
    "__version__",
    "VelaError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "ConcurrencyError",
    "ExternalServiceError",
    "to_decimal",
    "round_half_up",
    "sum_amounts",
    "allocate_pro_rata",
    "order_sn",
    "refund_sn",
    "settlement_sn",
    "trace_id",
    "build_key",
    "normalize_token",
    "make_event",
    "EventBatch",
    "StateMachine",
]

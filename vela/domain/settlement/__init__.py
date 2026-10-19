"""settlement 域。结算/账期/对账。

和 order 域同款规矩:高频 API 从包根 re-export,别从子模块深层
import;跨域数据(订单行、商户费率表)一律参数传入,不 import
其他业务域。

已知问题 #VT-2217(幂等键没带 merchant scope)详见 README.md,
新代码构造幂等键必须带 scope。
"""

from vela.domain.settlement.events import (
    EVENT_SETTLEMENT_PUSHED,
    EVENT_SETTLEMENT_RECONCILED,
    EVENT_SETTLEMENT_SETTLED,
    make_settlement_event,
)
from vela.domain.settlement.models import LineKind, SettlementLineModel, SettlementModel
from vela.domain.settlement.reconcile import diff_statements, emit_reconciled
from vela.domain.settlement.repository import SettlementRepository
from vela.domain.settlement.service import SettlementService
from vela.domain.settlement.statement import build_statement, orders_from_batches
from vela.domain.settlement.states import SettlementStateMachine, SettlementStatus
from vela.domain.settlement.terms import (
    DEFAULT_FEE_RATE,
    due_date,
    effective_terms,
    is_overdue,
)

__all__ = [
    "SettlementModel",
    "SettlementLineModel",
    "LineKind",
    "SettlementStatus",
    "SettlementStateMachine",
    "SettlementService",
    "SettlementRepository",
    "build_statement",
    "orders_from_batches",
    "diff_statements",
    "emit_reconciled",
    "due_date",
    "effective_terms",
    "is_overdue",
    "DEFAULT_FEE_RATE",
    "EVENT_SETTLEMENT_PUSHED",
    "EVENT_SETTLEMENT_SETTLED",
    "EVENT_SETTLEMENT_RECONCILED",
    "make_settlement_event",
]

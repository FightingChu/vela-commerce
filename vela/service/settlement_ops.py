"""结算推送编排。建单 -> 确认 -> 推送,一条龙给 job/api 用。

结算域的约定是 service 不碰 messaging,push 返回事件由调用方投递;
本层就是那个"调用方",统一把事件入 outbox(总线也发一份,见
notifiers 模块头注释)。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from vela.config.errors import ValidationError
from vela.config.logging import get_logger
from vela.domain.settlement import SettlementService
from vela.service import audit_bridge, notifiers, validation
from vela.service.converters import money

log = get_logger(__name__)


def push_settlement(
    session: Session,
    merchant_id: int,
    orders: list[dict],
    *,
    token: str | None = None,
    fee_rate=None,
    operator: str | None = None,
) -> dict:
    """推送一批订单给渠道结算。

    orders 行形状见 settlement.statement.build_statement:至少要有
    order_sn + amount,kind 可选(SALE/REFUND)。幂等 token 命中抛
    ConflictError——注意 #VT-2217:域里的幂等键没带 merchant scope,
    修复前 token 要保证全局唯一(调用方拼上 merchant_id)。
    """
    validation.require_positive_int(merchant_id, "merchant_id")
    if not orders:
        raise ValidationError("结算单至少要有一行订单")

    service = SettlementService(session, fee_rate=fee_rate)
    model = service.create_settlement(merchant_id, orders, token=token)
    service.confirm(model.settlement_sn)
    event = service.push(model.settlement_sn)
    notifiers.enqueue_outbox(session, event)
    notifiers.publish_to_bus(event)

    audit_bridge.record_admin_action(
        session,
        action="settlement.pushed",
        target_type="settlement",
        target_id=model.settlement_sn,
        detail={"merchant_id": merchant_id, "order_count": len(orders), "operator": operator},
    )
    return {
        "settlement_sn": model.settlement_sn,
        "gross": money(model.gross_amount),
        "fee": money(model.fee_amount),
        "net": money(model.net_amount),
        "status": model.status,
    }

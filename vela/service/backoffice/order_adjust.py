"""订单行调整。改价场景:客服补偿、拍错价救火。只放行 CREATED 单,
PAID 之后动金额一律走退款,这条红线别破。

改完必须 recompute_total,行金额和合计的守恒靠 aggregate 保证,
这里不自己算第二遍(算第二遍就会有两套口径)。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from vela.config.errors import NotFoundError, ValidationError
from vela.config.logging import get_logger
from vela.domain.order import Order, OrderRepository
from vela.service import audit_bridge
from vela.service.converters import money

log = get_logger(__name__)


def adjust_line_price(
    session: Session,
    order_sn: str,
    line_id: int,
    new_price,
    *,
    reason: str,
    operator: str | None = None,
) -> Order:
    """改行单价并重算合计。返回聚合(合计在 model.total_amount)。

    纯手动改价,不问价格中心——救火通道就是要能越过报价;留了审计,
    财务月度抽查 adjust 记录。
    """
    from vela.domain.shared import round_half_up, to_decimal

    if not reason:
        raise ValidationError("改价必须给原因(审计要求)")

    repo = OrderRepository(session)
    agg = Order(repo.get_by_sn(order_sn))
    if agg.status_name != "CREATED":
        raise ValidationError(
            f"只有 CREATED 单可以调整,当前 {agg.status_name}",
            detail={"order_sn": order_sn, "status": agg.status_name},
        )

    price = to_decimal(new_price)
    if price < 0:
        raise ValidationError(f"新单价不能为负: {price}")

    line = next((li for li in agg.lines if li.id == line_id), None)
    if line is None:
        raise NotFoundError(
            f"订单 {order_sn} 没有行 {line_id}",
            detail={"order_sn": order_sn, "line_id": line_id},
        )

    old_price = line.unit_price
    line.unit_price = price
    line.line_amount = round_half_up(price * line.qty)
    snapshot = dict(line.snapshot or {})
    # 快照里保留改价痕迹,拆单/导出时能看到原始成交价
    snapshot["price_adjusted"] = {
        "from": str(old_price),
        "to": str(price),
        "reason": reason,
        "operator": operator,
    }
    line.snapshot = snapshot

    agg.recompute_total()
    note = f"adjust:{line_id}:{reason}"
    agg.model.remark = f"{agg.model.remark};{note}" if agg.model.remark else note
    session.flush()

    audit_bridge.record_admin_action(
        session,
        action="order.line_price_adjusted",
        target_type="order_line",
        target_id=line_id,
        detail={
            "order_sn": order_sn,
            "from": str(old_price),
            "to": str(price),
            "total_after": money(agg.model.total_amount),
            "reason": reason,
            "operator": operator,
        },
    )
    log.info(
        "line_price_adjusted",
        order_sn=order_sn,
        line_id=line_id,
        total=money(agg.model.total_amount),
    )
    return agg

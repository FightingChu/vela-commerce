"""下单链路的券核销编排。券怎么算(promotion/rules.py)和订单怎么摊
(Order.aggregate)各归各域,这里只负责把两边接起来。

顺序有讲究:先核销(可能抛券不可用/超限),再摊钱——核销失败订单
原封不动;反过来先摊钱,券挂了还得回滚分摊,多一段没必要的补偿。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from vela.config.errors import ValidationError
from vela.config.logging import get_logger
from vela.domain.order import Order, OrderRepository
from vela.domain.promotion import CouponService
from vela.service import audit_bridge, validation
from vela.service.converters import money

log = get_logger(__name__)


def apply_coupon_to_order(
    session: Session,
    order_sn: str,
    code: str,
    *,
    token: str | None = None,
    operator: str | None = None,
) -> dict:
    """对 CREATED 单核销一张券,优惠按行金额权重摊下去。

    返回 {"order_sn","code","discount","total"}。重复请求由
    CouponService 的 (coupon, customer, order_sn) 唯一键幂等。
    """
    validation.require_sn(order_sn)
    validation.require_non_empty_str(code, "code")

    repo = OrderRepository(session)
    agg = Order(repo.get_by_sn(order_sn))
    if agg.status_name != "CREATED":
        raise ValidationError(
            f"只有 CREATED 单可以核销优惠券,当前 {agg.status_name}",
            detail={"order_sn": order_sn, "status": agg.status_name},
        )

    svc = CouponService(session)
    discount = svc.redeem(
        code,
        str(agg.model.customer_id),
        order_sn,
        agg.model.total_amount,
        token=token,
    )

    # 剩余金额不小于 0 由 rules.apply 的钳制保证(优惠最多抵到订单额)
    agg.allocate_discount(discount)
    session.flush()

    audit_bridge.record_admin_action(
        session,
        action="order.coupon_applied",
        target_type="order",
        target_id=order_sn,
        detail={"code": code, "discount": str(discount), "operator": operator},
    )
    return {
        "order_sn": order_sn,
        "code": code,
        "discount": money(discount),
        "total": money(agg.model.total_amount),
    }


def release_order_coupons(session: Session, order_sn: str) -> int:
    """整单退券(取消/退款链路用)。返回释放的核销记录数,0 也算成功。"""
    validation.require_sn(order_sn)
    released = CouponService(session).release(order_sn)
    if released:
        audit_bridge.record_admin_action(
            session,
            action="order.coupons_released",
            target_type="order",
            target_id=order_sn,
            detail={"count": len(released)},
        )
    return len(released)


def coupon_view(session: Session, code: str) -> dict | None:
    """券详情(管理端/详情页)。查无返回 None。"""
    coupon = CouponService(session).coupon_by_code(code)
    if coupon is None:
        return None
    return {
        "code": coupon.code,
        "title": coupon.title,
        "kind": coupon.kind.value if hasattr(coupon.kind, "value") else str(coupon.kind),
        "enabled": coupon.enabled,
        "total_quota": coupon.total_quota,
        "used_quota": coupon.used_quota,
        "remaining_quota": coupon.remaining_quota,
    }

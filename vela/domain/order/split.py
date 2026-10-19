"""拆单。多仓发货场景:选中行拆到子单,父单保留剩余行。

只在 CREATED 档拆(父单必须是 CREATED)。金额守恒:
- 父单优惠按"选中行金额 vs 保留行金额"的权重劈成两份(allocate_pro_rata)
- 每份再在各自单内按行金额分摊到 discount_share
- 所以 父合计 + 子合计 == 原合计,优惠也严格守恒(对账要求)

行模型是复用的(直接挪 order_id),没有复制行,快照跟着走。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from vela.config.errors import ValidationError
from vela.domain.shared import ZERO, SerialGenerator, allocate_pro_rata, sum_amounts
from vela.domain.shared import order_sn as make_order_sn
from vela.domain.order.aggregate import Order
from vela.domain.order.events import EVENT_ORDER_SPLIT, build_order_event
from vela.domain.order.models import OrderModel
from vela.domain.order.order_errors import OrderStateError
from vela.domain.order.repository import OrderRepository
from vela.domain.order.states import OrderStatus

_SERIAL = SerialGenerator()


def split_order(session: Session, order_sn: str, line_indexes: list[int]) -> tuple[Order, Order]:
    """把 line_indexes(行下标,按 id 升序从 0 数)选中的行拆成子单。

    返回 (parent, child)。状态同父单档——目前只放行 CREATED。
    """
    repo = OrderRepository(session)
    parent_agg = Order(repo.get_by_sn(order_sn))

    # 状态机没有"拆单"这条边(拆单不改状态),所以这里只做档位校验:
    # 目前只放行 CREATED。以后要支持 PAID 拆单,先去 states.py 讨论,
    # 别绕过这里——#VT-2044
    if parent_agg.status_name != "CREATED":
        raise OrderStateError(
            f"只有 CREATED 可拆单,当前 {parent_agg.status_name}",
            detail={"order_sn": order_sn, "status": parent_agg.status_name},
        )

    lines = parent_agg.lines
    idx_set = set(line_indexes)
    if not idx_set:
        raise ValidationError("line_indexes 不能为空")
    if any(not isinstance(i, int) or i < 0 or i >= len(lines) for i in idx_set):
        raise ValidationError(
            f"行下标越界: {sorted(idx_set)}(共 {len(lines)} 行)", detail={"line_count": len(lines)}
        )
    if len(idx_set) >= len(lines):
        raise ValidationError("不能把所有行都拆走,父单会变空单")

    picked = [lines[i] for i in sorted(idx_set)]
    kept = [line for i, line in enumerate(lines) if i not in idx_set]

    parent_model = parent_agg.model
    total_discount = parent_model.discount_amount or ZERO

    picked_amount = sum_amounts(*(line.line_amount for line in picked))
    kept_amount = sum_amounts(*(line.line_amount for line in kept))
    child_discount, parent_discount = allocate_pro_rata(total_discount, [picked_amount, kept_amount])

    child_model = OrderModel(
        # 参数 order_sn 把工厂函数遮住了,别名 import 一下
        order_sn=make_order_sn(_SERIAL.next_serial()),
        customer_id=parent_model.customer_id,
        status=OrderStatus.CREATED.value,
        currency=parent_model.currency,
        channel=parent_model.channel,
        total_amount=ZERO,
        discount_amount=ZERO,
        paid_amount=ZERO,
        remark=f"split-from:{order_sn}",
    )
    session.add(child_model)

    # 挪行:同一批 OrderLineModel 改挂子单
    for line in picked:
        parent_model.lines.remove(line)
        child_model.lines.append(line)
    session.flush()

    child_agg = Order(child_model)
    # 父聚合的 lines 还是挪行前的旧列表,先重建再分摊,不然会把
    # 已经划走的行也摊进去
    parent_agg.lines = repo.load_lines(parent_model.id)
    child_agg.allocate_discount(child_discount)
    parent_agg.allocate_discount(parent_discount)

    parent_agg.events.append(
        build_order_event(
            EVENT_ORDER_SPLIT,
            parent_agg,
            {
                "child_order_sn": child_model.order_sn,
                "moved_line_count": len(picked),
                "child_discount": str(child_discount),
                "parent_discount": str(parent_discount),
            },
        )
    )
    session.flush()
    return parent_agg, child_agg

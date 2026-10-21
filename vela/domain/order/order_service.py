"""下单服务。

跨域能力(库存预占/询价)全部构造注入,order 域不 import 其他业务域:
- reserver: callable(sku_id, qty, order_sn) -> int,返回预占凭证(不透明,
  库存侧自己解释,释放时原样还回去)
- pricer: callable(sku_ids) -> dict[int, Decimal],缺价的 sku 由本域报
  ValidationError
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from vela.config.errors import ValidationError
from vela.domain.order.aggregate import Order
from vela.domain.order.events import EVENT_ORDER_CREATED, build_order_event
from vela.domain.order.models import OrderLineModel, OrderModel
from vela.domain.order.order_errors import DuplicateOrderError, OrderNotFoundError
from vela.domain.order.repository import OrderRepository
from vela.domain.order.states import OrderStatus
from vela.domain.shared import (
    ZERO,
    SerialGenerator,
    build_key,
    normalize_token,
    order_sn,
    round_half_up,
    to_decimal,
)

# 进程内序列,多实例下各自一段,见 shared/ids.py 的说明
_SERIAL = SerialGenerator()

#: 幂等标记前缀,存在 orders.remark 里
IDEM_PREFIX = "idem:"


class OrderService:
    def __init__(
        self,
        session: Session,
        *,
        reserver=None,
        pricer=None,
    ):
        self.session = session
        self.reserver = reserver
        self.pricer = pricer

    # ---- 读 ----

    def get_order(self, order_sn: str) -> Order:
        repo = OrderRepository(self.session)
        try:
            model = repo.get_by_sn(order_sn)
        except OrderNotFoundError:
            raise
        return Order(model)

    # ---- 写 ----

    def create_order(
        self,
        customer_id: int,
        lines: list[dict],
        *,
        channel: str = "app",
        token=None,
        trace: str | None = None,
    ) -> Order:
        if not customer_id:
            raise ValidationError("customer_id 不能为空")
        if not lines:
            raise ValidationError("订单至少要有一行")

        parsed = self._parse_lines(lines)

        # 幂等:临时方案是把 key 塞在 remark 里("idem:<scope>:<token>"),
        # 查同 key 的 CREATED 单存在即认为重复。正式幂等表(带 TTL)
        # 见 #VT-2101 与 vela/service/idempotency_store.py,别再新增
        # 依赖 remark 标记的调用方。
        marker = None
        if normalize_token(token):
            key = build_key("order_create", token)
            marker = f"{IDEM_PREFIX}{key}"
            existing = OrderRepository(self.session).find_by_remark_marker(
                marker, status=OrderStatus.CREATED
            )
            if existing is not None:
                raise DuplicateOrderError(
                    "重复的下单请求(幂等 token 命中)",
                    detail={"order_sn": existing.order_sn, "idem_key": key},
                )

        model = OrderModel(
            order_sn=order_sn(_SERIAL.next_serial()),
            customer_id=customer_id,
            status=OrderStatus.CREATED.value,
            channel=channel or "app",
            total_amount=ZERO,
            discount_amount=ZERO,
            paid_amount=ZERO,
            remark=marker,
        )

        for item in parsed:
            snapshot = {
                "sku_id": item["sku_id"],
                "qty": item["qty"],
                "unit_price": str(item["unit_price"]),
                "name": None,  # 展示字段由上游 enrichment 填,#VT-2144
            }
            # 预占。reserver 没注入就裸建单(降级路径,预占缺口由调用方
            # 兜底,别在生产上这么组装——#VT-1902 复盘里提过)
            if self.reserver is not None:
                snapshot["reservation_ref"] = self.reserver(
                    item["sku_id"], item["qty"], model.order_sn
                )
            model.lines.append(
                OrderLineModel(
                    order_id=None,
                    sku_id=item["sku_id"],
                    qty=item["qty"],
                    unit_price=item["unit_price"],
                    line_amount=item["line_amount"],
                    discount_share=ZERO,
                    snapshot=snapshot,
                )
            )

        agg = Order(model)
        agg.recompute_total()
        self.session.add(model)
        self.session.flush()  # 拿 id / 让幂等查询可见

        agg.events.append(build_order_event(EVENT_ORDER_CREATED, agg, trace=trace))
        return agg

    # ---- 内部 ----

    def _parse_lines(self, lines: list[dict]) -> list[dict]:
        sku_ids: list[int] = []
        cleaned: list[dict] = []
        for idx, raw in enumerate(lines):
            sku_id = raw.get("sku_id")
            qty = raw.get("qty")
            if not isinstance(sku_id, int) or isinstance(sku_id, bool):
                raise ValidationError(f"第 {idx} 行 sku_id 非法: {sku_id!r}")
            if not isinstance(qty, int) or qty <= 0:
                raise ValidationError(f"sku {sku_id} 的 qty 非法: {qty!r}")
            cleaned.append({"sku_id": sku_id, "qty": qty, "unit_price": raw.get("unit_price")})
            sku_ids.append(sku_id)

        # 询价补价:行里带 unit_price 的跳过,缺的问 pricer
        missing = [c for c in cleaned if c["unit_price"] is None]
        if missing:
            if self.pricer is None:
                raise ValidationError(
                    "缺少单价且未注入 pricer",
                    detail={"skus": sorted({c["sku_id"] for c in missing})},
                )
            price_map: dict[int, Decimal] = self.pricer([c["sku_id"] for c in missing])
            still_missing = [c["sku_id"] for c in missing if c["sku_id"] not in price_map]
            if still_missing:
                raise ValidationError(
                    "价格中心缺价,禁止裸价下单",
                    detail={"missing_skus": sorted(set(still_missing))},
                )
            for c in missing:
                c["unit_price"] = price_map[c["sku_id"]]

        for c in cleaned:
            unit_price = to_decimal(c["unit_price"])
            if unit_price < 0:
                raise ValidationError(f"sku {c['sku_id']} 单价不能为负")
            c["unit_price"] = unit_price
            c["line_amount"] = round_half_up(unit_price * c["qty"])
        return cleaned

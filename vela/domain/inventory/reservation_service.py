"""预占链路:reserve -> consume / 超时释放。

返回给调用方的是 ReservationModel 主键,当不透明凭证用,
别处不要对它的数值做任何假设(不是单号也不是序号段)。
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from vela.config.clocks import utc_now
from vela.config.constants import RESERVATION_DEFAULT_TTL
from vela.config.errors import ValidationError
from vela.db import current_session
from vela.domain.inventory import events as ev
from vela.domain.inventory.errors import InventoryShortageError, ReservationExpiredError
from vela.domain.inventory.reservation_model import ReservationModel, ReservationStatus
from vela.domain.inventory.reservation_repo import ReservationRepository
from vela.domain.inventory.stock_model import LedgerDirection
from vela.domain.inventory.stock_repo import StockRepository
from vela.domain.shared import make_event


def reserve(
    sku_id: int,
    qty: int,
    *,
    order_sn: str,
    warehouse: str = "MAIN",
    ttl_seconds: int | None = None,
    session: Session | None = None,
) -> int:
    """预占库存,返回预占号。"""
    if qty <= 0:
        raise ValidationError(f"预占数量必须为正: {qty}")
    session = session or current_session()
    stocks = StockRepository(session)
    rsvs = ReservationRepository(session)

    stock = stocks.get_or_create(sku_id, warehouse)
    if stock.available < qty:
        raise InventoryShortageError(sku_id, qty, stock.available)

    ttl = ttl_seconds if ttl_seconds is not None else RESERVATION_DEFAULT_TTL
    now = utc_now()
    rsv = ReservationModel(
        sku_id=sku_id,
        warehouse=warehouse,
        qty=qty,
        order_sn=order_sn,
        status=ReservationStatus.ACTIVE,
        ttl_seconds=ttl,
        expires_at=now + dt.timedelta(seconds=ttl),
    )
    rsvs.add(rsv)
    session.flush()  # 先拿到主键再挂事件
    stock.reserved += qty
    session.info.setdefault("vela_events", []).append(
        make_event(
            ev.EVENT_STOCK_RESERVED,
            {
                "reservation_id": rsv.id,
                "sku_id": sku_id,
                "warehouse": warehouse,
                "qty": qty,
                "order_sn": order_sn,
                "ttl_seconds": ttl,
            },
            trace=order_sn,
        )
    )
    return rsv.id


def consume_reservation(
    reservation_id: int,
    order_sn: str | None = None,
    *,
    session: Session | None = None,
) -> ReservationModel:
    session = session or current_session()
    rsvs = ReservationRepository(session)
    stocks = StockRepository(session)

    rsv = rsvs.fetch(reservation_id)
    if rsv.status != ReservationStatus.ACTIVE:
        raise ValidationError(
            f"预占 {reservation_id} 状态 {rsv.status},不能消费",
            detail={"status": rsv.status},
        )
    if rsv.expires_at <= utc_now():
        raise ReservationExpiredError(
            f"预占 {reservation_id} 已于 {rsv.expires_at} 过期"
        )
    if order_sn is not None and rsv.order_sn != order_sn:
        raise ValidationError(
            f"预占 {reservation_id} 属于订单 {rsv.order_sn},与 {order_sn} 不匹配"
        )

    rsvs.consume(reservation_id)
    # reserved 已在 consume 里还回去,这里真正动 on_hand
    stock = stocks.get_or_create(rsv.sku_id, rsv.warehouse)
    if stock.on_hand < rsv.qty:
        # 理论上到不了这:预占时已校验。兜底,防的是 #VT-1987 那种并发窗口
        raise InventoryShortageError(rsv.sku_id, rsv.qty, stock.on_hand)
    ledger = stocks.apply_ledger(
        stock, LedgerDirection.OUT, rsv.qty, "reservation_consume", rsv.order_sn
    )
    session.flush()
    session.info.setdefault("vela_events", []).append(
        make_event(
            ev.EVENT_RESERVATION_CONSUMED,
            {
                "reservation_id": reservation_id,
                "sku_id": rsv.sku_id,
                "qty": rsv.qty,
                "order_sn": rsv.order_sn,
                "balance_after": ledger.balance_after,
            },
            trace=rsv.order_sn,
        )
    )
    return rsv


def release_expired(now: dt.datetime | None = None, *, session: Session | None = None) -> int:
    """超时 job 入口:批量把到期预占置 EXPIRED,返还的数量已由仓储回补。"""
    session = session or current_session()
    rsvs = ReservationRepository(session)
    due = rsvs.expire_due(now or utc_now())
    for rsv in due:
        session.info.setdefault("vela_events", []).append(
            make_event(
                ev.EVENT_RESERVATION_TIMED_OUT,
                {
                    "reservation_id": rsv.id,
                    "sku_id": rsv.sku_id,
                    "qty": rsv.qty,
                    "order_sn": rsv.order_sn,
                },
                trace=rsv.order_sn,
            )
        )
    return len(due)


def load_active(order_sn: str, sku_id: int, *, session: Session | None = None) -> ReservationModel | None:
    """下单链路按单查在占预占。"""
    session = session or current_session()
    return ReservationRepository(session).find_active(order_sn, sku_id)

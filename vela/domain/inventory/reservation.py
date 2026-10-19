"""预占:纯逻辑层实体与策略,不碰 SA。

落库形态是 reservation_model.ReservationModel,这层给下单链路在
内存里算 TTL / 剩余量用。#VT-1987 之后所有释放都走 remaining 校验。
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from vela.config.clocks import utc_now
from vela.config.constants import RESERVATION_DEFAULT_TTL


@dataclass
class Reservation:
    id: int
    sku_id: int
    warehouse: str
    qty: int
    order_sn: str
    ttl_seconds: int
    created_at: dt.datetime
    released_at: dt.datetime | None = None
    released_qty: int = 0

    @property
    def remaining(self) -> int:
        return self.qty - self.released_qty

    def is_expired(self, now: dt.datetime | None = None) -> bool:
        if now is None:
            now = utc_now()
        expires = self.created_at + dt.timedelta(seconds=self.ttl_seconds)
        return now >= expires


class ReservationPolicy:
    default_ttl = RESERVATION_DEFAULT_TTL

    def __init__(self, ttl: int | None = None):
        if ttl is not None:
            self.default_ttl = ttl


class FlashSaleReservationPolicy(ReservationPolicy):
    # 秒杀只锁 5 分钟,占着不放会把正常单挤死
    default_ttl = 300


class BulkReservationPolicy(ReservationPolicy):
    default_ttl = 3600

    def __init__(self, ttl: int | None = None):
        super().__init__(ttl)


# 部分释放,qty 超过剩余量直接拒
def release_partial(reservation: Reservation, qty: int) -> Reservation:
    if qty > reservation.remaining:
        raise ValueError(
            f"释放量 {qty} 超过剩余预占 {reservation.remaining}: rsv-{reservation.id}"
        )
    reservation.released_qty += qty
    if reservation.remaining <= 0:
        reservation.released_at = utc_now()
    return reservation


# 给风控用的
def as_token(reservation: Reservation) -> str:
    return f"rsv-{reservation.id}"

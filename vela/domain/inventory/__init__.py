"""库存域。import 本包即注册全部表到 Base.metadata。"""

from __future__ import annotations

from vela.domain.inventory.events import (
    EVENT_RECONCILE_DONE,
    EVENT_RESERVATION_CONSUMED,
    EVENT_RESERVATION_RELEASED,
    EVENT_RESERVATION_TIMED_OUT,
    EVENT_STOCK_DEDUCTED,
    EVENT_STOCK_RESERVED,
)
from vela.domain.inventory.errors import (
    InventoryShortageError,
    ReservationExpiredError,
    ReservationNotFoundError,
)
from vela.domain.inventory.item_model import SkuModel
from vela.domain.inventory.reservation_model import ReservationModel, ReservationStatus
from vela.domain.inventory.reservation_repo import ReservationRepository
from vela.domain.inventory.reservation_service import (
    consume_reservation,
    load_active,
    release_expired,
    reserve,
)
from vela.domain.inventory.stock_model import (
    LedgerDirection,
    StockLedgerModel,
    StockModel,
)
from vela.domain.inventory.stock_repo import StockRepository
from vela.domain.inventory.stock_service import deduct, rollback
from vela.domain.inventory import reconcile

__all__ = [
    "SkuModel",
    "StockModel",
    "StockLedgerModel",
    "LedgerDirection",
    "ReservationModel",
    "ReservationStatus",
    "StockRepository",
    "ReservationRepository",
    "reserve",
    "consume_reservation",
    "release_expired",
    "load_active",
    "deduct",
    "rollback",
    "reconcile",
    "InventoryShortageError",
    "ReservationExpiredError",
    "ReservationNotFoundError",
    "EVENT_STOCK_RESERVED",
    "EVENT_STOCK_DEDUCTED",
    "EVENT_RESERVATION_CONSUMED",
    "EVENT_RESERVATION_RELEASED",
    "EVENT_RESERVATION_TIMED_OUT",
    "EVENT_RECONCILE_DONE",
]

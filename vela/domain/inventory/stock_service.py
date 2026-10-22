"""库存扣减/回滚。入口只有这两个,别的路径改 on_hand 一律违规。

事件挂到 session.info["vela_events"],请求收尾时中间件统一取走发
outbox——这里不直接 publish,事务回滚了事件不能留在外面。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from vela.db import current_session
from vela.domain.inventory.errors import InventoryShortageError
from vela.domain.inventory.events import EVENT_STOCK_DEDUCTED, EVENT_STOCK_ROLLED_BACK
from vela.domain.inventory.stock_model import LedgerDirection, StockLedgerModel, StockModel
from vela.domain.inventory.stock_repo import StockRepository
from vela.domain.shared import make_event

EVENTS_KEY = "vela_events"


def _emit(session: Session, event: dict) -> None:
    session.info.setdefault(EVENTS_KEY, []).append(event)


def collect_events(session: Session) -> list[dict]:
    """中间件/job 收尾用。取出并清空。"""
    events = list(session.info.get(EVENTS_KEY, []))
    session.info[EVENTS_KEY] = []
    return events


def deduct(
    sku_id: int,
    qty: int,
    ref_sn: str,
    warehouse: str = "MAIN",
    *,
    session: Session | None = None,
) -> tuple[StockModel, StockLedgerModel]:
    if qty <= 0:
        raise ValueError(f"扣减数量必须为正: {qty}")
    session = session or current_session()
    repo = StockRepository(session)
    stock = repo.get_or_create(sku_id, warehouse)
    if stock.on_hand < qty:
        raise InventoryShortageError(sku_id, qty, stock.on_hand)
    ledger = repo.apply_ledger(stock, LedgerDirection.OUT, qty, "deduct", ref_sn)
    session.flush()
    _emit(
        session,
        make_event(
            EVENT_STOCK_DEDUCTED,
            {
                "sku_id": sku_id,
                "warehouse": warehouse,
                "qty": qty,
                "ref_sn": ref_sn,
                "balance_after": ledger.balance_after,
            },
            trace=ref_sn,
        ),
    )
    return stock, ledger


def rollback(
    sku_id: int,
    qty: int,
    ref_sn: str,
    warehouse: str = "MAIN",
    *,
    session: Session | None = None,
) -> tuple[StockModel, StockLedgerModel]:
    if qty <= 0:
        raise ValueError(f"回滚数量必须为正: {qty}")
    session = session or current_session()
    repo = StockRepository(session)
    stock = repo.get_or_create(sku_id, warehouse)
    ledger = repo.apply_ledger(stock, LedgerDirection.IN, qty, "rollback", f"{ref_sn}:rb")
    session.flush()
    _emit(
        session,
        make_event(
            EVENT_STOCK_ROLLED_BACK,
            {"sku_id": sku_id, "warehouse": warehouse, "qty": qty, "ref_sn": ref_sn},
            trace=ref_sn,
        ),
    )
    return stock, ledger

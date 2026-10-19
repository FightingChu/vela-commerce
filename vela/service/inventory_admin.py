"""库存管理端操作。盘点调整 + 台账查询。

调整必须走台账(apply_ledger),裸改 on_hand 是 #VT-1987 的原案发现场,
code review 见一次打回一次。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from vela.config.errors import ValidationError
from vela.config.logging import get_logger
from vela.domain.inventory.stock_model import LedgerDirection, StockLedgerModel, StockModel
from vela.domain.inventory.stock_repo import StockRepository
from vela.service import audit_bridge

log = get_logger(__name__)


def adjust_stock(
    session: Session,
    sku_id: int,
    delta: int,
    reason: str,
    *,
    warehouse: str = "MAIN",
    ref_sn: str | None = None,
    operator: str | None = None,
) -> StockModel:
    """盘点调整。delta 正负都收,调整后 on_hand 不能为负、不能低于
    在占量(否则在占预占消费时会穿仓)。

    行里带 ref_sn 的(盘亏对应某张单)会记进台账,对账按它串。
    """
    if not isinstance(delta, int) or isinstance(delta, bool) or delta == 0:
        raise ValidationError(f"调整量必须是非零整数: {delta!r}")
    if not reason:
        raise ValidationError("盘点调整必须给原因")

    repo = StockRepository(session)
    stock = repo.get_or_create(sku_id, warehouse)
    new_on_hand = stock.on_hand + delta
    if new_on_hand < 0:
        raise ValidationError(
            f"调整后 on_hand 为负: {new_on_hand}",
            detail={"sku_id": sku_id, "warehouse": warehouse, "delta": delta},
        )
    if new_on_hand < stock.reserved:
        raise ValidationError(
            f"调整后 on_hand({new_on_hand})低于在占量({stock.reserved})",
            detail={"sku_id": sku_id, "warehouse": warehouse},
        )

    direction = LedgerDirection.IN if delta > 0 else LedgerDirection.OUT
    repo.apply_ledger(stock, direction, abs(delta), f"manual_adjust:{reason}", ref_sn)
    session.flush()

    audit_bridge.record_admin_action(
        session,
        action="inventory.adjusted",
        target_type="stock",
        target_id=f"{sku_id}@{warehouse}",
        detail={"delta": delta, "reason": reason, "operator": operator},
    )
    log.info(
        "stock_adjusted",
        sku_id=sku_id,
        warehouse=warehouse,
        delta=delta,
        balance_after=stock.on_hand,
    )
    return stock


def stock_ledger(
    session: Session,
    sku_id: int,
    *,
    warehouse: str = "MAIN",
    limit: int = 50,
) -> list[StockLedgerModel]:
    """台账流水,新的在前。balance_after 对账就靠它串。"""
    stmt = (
        select(StockLedgerModel)
        .where(
            StockLedgerModel.sku_id == sku_id,
            StockLedgerModel.warehouse == warehouse,
        )
        .order_by(StockLedgerModel.id.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars())


def stock_row(session: Session, sku_id: int, warehouse: str = "MAIN") -> StockModel | None:
    """裸查余额行,管理端详情页用。没有返回 None,不建空行。"""
    stmt = select(StockModel).where(
        StockModel.sku_id == sku_id,
        StockModel.warehouse == warehouse,
    )
    return session.execute(stmt).scalar_one_or_none()

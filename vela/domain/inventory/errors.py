"""库存域错误码。新码先去 docs/error-codes.md 登记。"""

from __future__ import annotations

from vela.config.errors import ConflictError, NotFoundError


class InventoryShortageError(ConflictError):
    """库存不足。detail 里带 sku 和缺口,运营看告警直接知道差多少。"""

    code = "inventory.0409"

    def __init__(self, sku_id, requested: int, available: int):
        shortage = requested - available
        super().__init__(
            f"库存不足: sku={sku_id} 需 {requested} 可用 {available},缺 {shortage}",
            detail={
                "sku_id": sku_id,
                "requested": requested,
                "available": available,
                "shortage": shortage,
            },
        )


class ReservationExpiredError(ConflictError):
    code = "inventory.0410"


class ReservationNotFoundError(NotFoundError):
    code = "inventory.0404"

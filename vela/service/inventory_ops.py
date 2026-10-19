"""库存查询。api 并行任务的契约模块:stock_view 签名一字不动。

只读视图,sku 没有库存行时返回全 0(购物车/详情页高频调用,
不能因为没初始化过库存就 404);也不顺手 get_or_create——查询路径
插空行的老毛病在 #VT-2210 记过一笔。
"""

from __future__ import annotations

from sqlalchemy import select

from vela.db import session_scope
from vela.domain.inventory.stock_model import StockModel

_scope = session_scope

_EMPTY = {"on_hand": 0, "reserved": 0, "available": 0}


def _find(session, sku_id: int, warehouse: str) -> StockModel | None:
    stmt = select(StockModel).where(
        StockModel.sku_id == sku_id,
        StockModel.warehouse == warehouse,
    )
    return session.execute(stmt).scalar_one_or_none()


def stock_view(sku_id: int, *, warehouse: str = "MAIN") -> dict:
    """{"sku_id","warehouse","on_hand","reserved","available"}。

    available 是算出来的(on_hand - reserved),库 里没有这列,
    #VT-1987 之前落过,两处更新打架出过超卖。
    """
    with _scope() as session:
        stock = _find(session, sku_id, warehouse)
        if stock is None:
            return {
                "sku_id": sku_id,
                "warehouse": warehouse,
                **_EMPTY,
            }
        return {
            "sku_id": stock.sku_id,
            "warehouse": stock.warehouse,
            "on_hand": stock.on_hand,
            "reserved": stock.reserved,
            "available": stock.available,
        }

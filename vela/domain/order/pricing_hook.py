"""询价钩子的兜底实现。

给测试和上层组装用:直接喂一张 dict 价格表,不过价格中心。
缺价的 sku 静默跳过(返回子集),要不要报错由 OrderService 决定。
生产组装顺序见 app/boot.py:RealPricer(走 pricing 域)优先,
挂了降级 flag 才落到这个。
"""

from __future__ import annotations

from decimal import Decimal

from vela.domain.shared import to_decimal


class DefaultPricer:
    def __init__(self, price_map: dict[int, Decimal]):
        self._prices: dict[int, Decimal] = {
            int(sku_id): to_decimal(price) for sku_id, price in price_map.items()
        }

    def __call__(self, sku_ids) -> dict[int, Decimal]:
        wanted = [int(s) for s in sku_ids]
        return {sku_id: self._prices[sku_id] for sku_id in wanted if sku_id in self._prices}

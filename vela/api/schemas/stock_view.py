"""库存视图。available 是算出来的,不落库。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StockView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku_id: int
    warehouse: str
    on_hand: int
    reserved: int
    available: int

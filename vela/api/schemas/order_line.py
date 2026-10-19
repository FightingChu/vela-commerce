"""下单行入参。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OrderLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: int = Field(gt=0)
    qty: int = Field(gt=0)

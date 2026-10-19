"""库存预占入参。ttl 不传走 RESERVATION_DEFAULT_TTL。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ReservationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: int = Field(gt=0)
    qty: int = Field(gt=0)
    order_sn: str = Field(min_length=1, max_length=64)
    warehouse: str = "MAIN"
    ttl_seconds: int | None = Field(default=None, gt=0)

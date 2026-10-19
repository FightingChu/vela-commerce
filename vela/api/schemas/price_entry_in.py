"""价格册条目入参。effective_to 为空表示长期有效。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from vela.api.schemas.base import Money


class PriceEntryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: int = Field(gt=0)
    list_price: Money
    sale_price: Money | None = None
    currency: str = "CNY"
    channel: str = ""
    effective_from: dt.datetime
    effective_to: dt.datetime | None = None

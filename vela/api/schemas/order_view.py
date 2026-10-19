"""订单视图。金额出参全是 str。"""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict

from vela.api.schemas.base import Money


class OrderView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_sn: str
    customer_id: int
    status: str
    currency: str = "CNY"
    total_amount: Money
    discount_amount: Money
    paid_amount: Money
    channel: str = "app"
    paid_at: dt.datetime | None = None
    created_at: dt.datetime | None = None

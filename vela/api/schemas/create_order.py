"""下单入参。checkout 端点专用,结构对齐 service 契约的 lines 项。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from vela.api.schemas.order_line import OrderLineIn


class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: int = Field(gt=0)
    lines: list[OrderLineIn] = Field(min_length=1)
    channel: str = "app"
    # 幂等 token,透传给 service 层,HTTP 层不解释
    token: str | None = None

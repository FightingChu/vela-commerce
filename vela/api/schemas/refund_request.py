"""退款申请入参。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from vela.api.schemas.base import Money


class RefundRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_sn: str = Field(min_length=1)
    amount: Money
    reason: str = Field(min_length=1, max_length=255)
    token: str | None = None

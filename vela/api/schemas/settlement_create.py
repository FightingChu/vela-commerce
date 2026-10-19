"""结算单创建入参。

orders 行结构对齐 settlement/statement.build_statement:
{"order_sn": str, "amount": str, "kind": "sale"/"refund"}。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SettlementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant_id: int = Field(gt=0)
    orders: list[dict] = Field(min_length=1)
    token: str | None = None
    terms_days: int | None = Field(default=None, ge=1, le=365)

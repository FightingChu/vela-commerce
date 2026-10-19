"""建券入参。kind 语义见 promotion/coupon_model.py 的注释。"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from vela.api.schemas.base import Money


class CouponCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    kind: Literal["THRESHOLD", "DISCOUNT", "NO_THRESHOLD"]
    threshold_amount: Money = "0"
    discount_amount: Money = "0"
    # 3 位小数,0.123 = 8.77 折;str 传输,域层 to_decimal
    discount_rate: str = "0"
    stackable: bool = False
    total_quota: int = Field(gt=0)
    per_customer_limit: int = Field(default=1, ge=1)
    valid_from: dt.datetime | None = None
    valid_to: dt.datetime | None = None

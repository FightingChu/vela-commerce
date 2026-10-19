"""券视图。出参不带 threshold/rate 细节,运营后台另走内部接口。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CouponView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    title: str
    kind: str
    stackable: bool = False
    total_quota: int
    used_quota: int
    remaining_quota: int
    enabled: bool = True

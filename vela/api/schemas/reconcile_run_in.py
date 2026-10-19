"""对账入参。

expected 的键是 "sku_id:warehouse" 字符串(db 层快照键是 tuple,
HTTP 传输里序列化成冒号拼的字符串,写死在这里,客户端别自造)。
expected 不传就只出快照不比对。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ReconcileRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected: dict[str, int] | None = None
    warehouse: str = "MAIN"
    dry_run: bool = True

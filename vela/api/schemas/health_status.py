"""/healthz 响应体。db/bus 任一挂了 status 就是 degraded,但仍是 200。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "degraded"]
    db: bool
    bus: bool

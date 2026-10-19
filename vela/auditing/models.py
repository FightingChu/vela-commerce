"""审计日志表。只写不改,合规导出和告警排查都查这里。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from vela.db import Base, JsonColumn, PkMixin, TenantColumnMixin, TimestampMixin


class AuditLogModel(Base, PkMixin, TimestampMixin, TenantColumnMixin):
    """单条审计事件。target_* 指向被操作对象,不建 FK(跨域,删了也别牵连)。"""

    actor: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JsonColumn, nullable=True)
    # 网关注入的 trace id,排查时和 APM 对齐;后台任务可能没有
    trace: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

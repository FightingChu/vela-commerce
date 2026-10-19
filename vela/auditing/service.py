"""审计写入服务。业务侧唯一入口,别直接 new AuditLogModel。"""

from __future__ import annotations

from typing import Any

from vela.auditing.context import current
from vela.auditing.redaction import redact_detail
from vela.auditing.sink import DbSink, Sink
from vela.config.clocks import utc_now
from vela.config.logging import get_logger

log = get_logger(__name__)

# 定时任务/系统触发的操作没有登录态,actor 统一记这个,报表口径认它
SYSTEM_ACTOR = "system"


class AuditService:
    """actor/trace/tenant 全部隐式取审计上下文,调用方不用传(也传不进来,
    这是设计约束:防止调用点伪造 actor,见 ADR-0011)。"""

    def __init__(self, session, sink: Sink | None = None):
        self.session = session
        self.sink = sink or DbSink(session)

    def record(
        self,
        action: str,
        target_type: str,
        target_id: Any,
        detail: dict | None = None,
    ) -> dict:
        """写一条审计记录,返回落盘的 record(测试断言用)。"""
        ctx = current()
        if ctx is None:
            # 没绑上下文不报错,审计不能挡业务,但要能从日志里发现
            log.warning("audit_without_context", action=action, target=target_id)
            actor = SYSTEM_ACTOR
            trace = None
            tenant = None
            at = utc_now()
        else:
            actor = ctx.actor
            trace = ctx.trace
            tenant = ctx.tenant
            at = ctx.at or utc_now()

        # 落盘前统一过脱敏,防止调用方把明文手机号塞进 detail
        safe_detail = redact_detail(detail or {})

        record = {
            "actor": actor,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "detail": safe_detail,
            "trace": trace,
            "tenant": tenant,
            "at": at.isoformat() if hasattr(at, "isoformat") else str(at),
        }
        self.sink.write(record)
        return record

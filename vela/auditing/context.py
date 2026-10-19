"""隐式审计上下文,threading.local 实现。

中间件进请求时 bind,业务代码 current() 拿"现在是谁在干、哪条 trace"。
task 池里的后台任务要自己 re-bind,#VT-982 踩过坑(线程复用导致
上一个任务的 actor 挂到下一个任务的日志上)。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime

from vela.config.clocks import utc_now
from vela.config.errors import ValidationError

_local = threading.local()


@dataclass
class AuditContext:
    """一次操作的责任主体。at 为 None 表示绑定时没给时间。"""

    actor: str
    trace: str | None = None
    tenant: str | None = None
    at: datetime | None = None


def bind(actor: str, trace: str | None = None, tenant: str | None = None) -> AuditContext:
    """绑定到当前线程;重复 bind 覆盖旧值,不叠加(嵌套调用请自己 save/restore)。"""
    ctx = AuditContext(actor=actor, trace=trace, tenant=tenant, at=utc_now())
    _local.ctx = ctx
    return ctx


def current() -> AuditContext | None:
    return getattr(_local, "ctx", None)


def unbind() -> None:
    if hasattr(_local, "ctx"):
        del _local.ctx


def redact(value: str) -> str:
    # 首尾各留 2 位,中间全打星;太短的连长度都别暴露,统一按长度打满
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


def child(actor: str) -> AuditContext:
    # 子操作换人不换链路:trace/tenant 继承当前上下文,时间取现在
    parent = current()
    if parent is None:
        raise ValidationError("没有当前审计上下文,无法派生 child")
    return AuditContext(actor=actor, trace=parent.trace, tenant=parent.tenant, at=utc_now())

"""job 运行上下文:trace 生成与透传。

job 没有请求头可拿,trace 自己造。格式 job-<名字>-<随机>,
审计上下文没绑(actor 缺省落 system),这里只管 trace 一条线,
方便把一次任务触发的所有 outbox 事件串起来排障。
"""

from __future__ import annotations

import contextlib
import contextvars
import secrets
from dataclasses import dataclass, field

from vela.config.clocks import utc_now

_trace_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("vela_job_trace", default=None)


def new_trace(name: str) -> str:
    return f"job-{name}-{secrets.token_hex(4)}"


def bind_trace(trace: str):
    """绑定并返回 token,结束时 reset_trace(token)。"""
    return _trace_var.set(trace)


def reset_trace(token) -> None:
    _trace_var.reset(token)


def current_trace() -> str | None:
    return _trace_var.get()


@dataclass
class JobContext:
    """留给以后手工触发时带参用的。现在 runner 直调,还没排上。#VT-2228"""

    name: str
    trace: str = field(default_factory=lambda: "")
    started_at: object = field(default_factory=utc_now)
    trigger: str = "manual"  # cron / manual / api


@contextlib.contextmanager
def job_session(session=None):
    """任务里拿 DB 会话的统一口子。

    线上不传参走 session_scope(自带 commit/rollback);测试和
    手工脚本直接把 session 塞进来,生命周期归调用方管。
    延迟 import,包 import 时不碰 DB。
    """
    if session is not None:
        yield session
        return
    from vela.db.session import session_scope

    with session_scope() as s:
        yield s

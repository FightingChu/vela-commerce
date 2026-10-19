"""Flask 预留钩子。

app 侧还没接(排期见 #VT-880),但头协议先在这里定死,
其他模块别自己去读 X-Vela-* 头。注意这里不 import flask,
拿的是纯 dict headers,方便 WSGI 之外的入口复用。
"""

from __future__ import annotations

from vela.auditing.context import AuditContext, bind, unbind
from vela.config.constants import TENANT_HEADER, TRACE_HEADER

# 网关还没透传 actor,先留常量;没有就记 anonymous
ACTOR_HEADER = "X-Vela-Actor"
ANONYMOUS_ACTOR = "anonymous"


def on_request_start(headers: dict) -> AuditContext:
    """请求进入:从 trace/tenant 头绑审计上下文,返回绑好的 ctx。"""
    trace = headers.get(TRACE_HEADER) or None
    tenant = headers.get(TENANT_HEADER) or None
    actor = headers.get(ACTOR_HEADER) or ANONYMOUS_ACTOR
    return bind(actor, trace=trace, tenant=tenant)


def on_request_end() -> None:
    """请求结束(含异常路径,after_teardown 里调),解绑防线程复用串号。"""
    unbind()

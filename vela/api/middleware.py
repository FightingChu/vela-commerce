"""请求级横切:trace/租户头、审计上下文、请求 session。

头协议和 auditing.middleware 保持一致(那边是纯 dict 版,给 job 用),
这边是 Flask 侧的实现。X-Vela-Trace-Id 没带就现生成一个并在响应里
回写,网关日志靠这个对齐;X-Vela-Tenant 缺省落 DEFAULT_TENANT,
healthz 这类公开端点也一样走,不特判。
"""

from __future__ import annotations

import contextlib

from flask import g, request

from vela.auditing.middleware import on_request_end, on_request_start
from vela.config.constants import TENANT_HEADER, TRACE_HEADER
from vela.db import DEFAULT_TENANT, current_session, tenant_context
from vela.domain.shared.ids import trace_id as new_trace_id


def register_middleware(app) -> None:
    app.before_request(_before_request)
    app.after_request(_after_request)
    app.teardown_appcontext(_teardown)


def _before_request() -> None:
    trace = request.headers.get(TRACE_HEADER) or new_trace_id()
    tenant = request.headers.get(TENANT_HEADER) or DEFAULT_TENANT
    g.trace_id = trace
    g.tenant_id = tenant

    # 审计上下文允许匿名,租户上下文不合法直接抛 TenantError(403)
    on_request_start({TRACE_HEADER: trace, TENANT_HEADER: tenant})
    g.tenant_cm = tenant_context(tenant)
    g.tenant_cm.__enter__()


def _after_request(resp):
    trace = getattr(g, "trace_id", None)
    if trace:
        resp.headers[TRACE_HEADER] = trace
    return resp


def _teardown(_exc) -> None:
    # tenant_cm 在 before 里手动 enter,这里手动 exit;异常路径也要走
    cm = g.get("tenant_cm")
    if cm is not None:
        with contextlib.suppress(Exception):
            cm.__exit__(None, None, None)
    sess = g.get("db_session")
    if sess is not None:
        sess.close()
    on_request_end()


def db():
    """请求级 session,懒创建。读 handler 直接用;写完记得 commit()。

    不用 session_scope() 是因为 teardown 统一 close,两层管理会打架。
    """
    if "db_session" not in g:
        g.db_session = current_session()
    return g.db_session

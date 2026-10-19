"""trace 串联。service 层入口统一在这里补 trace,别散到各域。

网关没带 trace 头时本地生成一个(伪随机,只做日志串联);
子调用用 child_trace 挂后缀,排查时能看出调用层级。
"""

from __future__ import annotations

from vela.config.constants import TRACE_HEADER
from vela.domain.shared import trace_id as generate_trace_id

#: 单段 trace 的长度上限,超了截断(日志列宽是拍脑袋定的 64)
MAX_TRACE_LEN = 64


def ensure_trace(trace: str | None) -> str:
    """空/纯空白的 trace 换成本地生成的。老网关偶尔发 "-1",也当空处理。"""
    if trace is None:
        return generate_trace_id()
    cleaned = trace.strip()
    if not cleaned or cleaned == "-1":
        return generate_trace_id()
    return cleaned


def child_trace(parent: str | None, tag: str) -> str:
    """子调用 trace:parent>tag。parent 没有就从 tag 起头。"""
    tag = (tag or "").strip() or "step"
    base = (parent or "").strip() or generate_trace_id()
    combined = f"{base}>{tag}"
    return combined[:MAX_TRACE_LEN]


def header_name() -> str:
    """给 http 层用的常量透传,免得业务代码直接 import config。"""
    return TRACE_HEADER

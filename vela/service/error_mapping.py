"""错误 -> 对外响应的统一翻译。api 并行任务直接消费这里的形状,
http 层不要再自己拼 body(拼过三版,字段名都不一样,2025-12 收敛的)。

service 内部不要 catch VelaError 之后吞掉或降级,让它们飞到边界来翻。
"""

from __future__ import annotations

from vela.config.errors import VelaError

#: 非 VelaError 的兜底码。detail 里不带原始异常文本,防止内部信息外漏
FALLBACK_CODE = "vela.9999"
FALLBACK_MESSAGE = "内部错误,请稍后重试"


def status_of(exc: Exception) -> int:
    if isinstance(exc, VelaError):
        return exc.http_status
    return 500


def to_payload(exc: Exception) -> dict:
    """异常 -> {"code","message","detail"}。VelaError 走 as_dict,其余兜底。"""
    if isinstance(exc, VelaError):
        return exc.as_dict()
    return {"code": FALLBACK_CODE, "message": FALLBACK_MESSAGE, "detail": {}}


def to_response(exc: Exception) -> tuple[dict, int]:
    """(body, http_status) 二元组,flask 层 jsonify 后直接返回。"""
    return to_payload(exc), status_of(exc)

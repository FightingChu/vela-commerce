"""值渲染:Column.fmt -> 导出字符串。

只服务 csv/Excel 导出。API 的 JSON 输出要原始值,别调这里
(#VT-2321,pct 列被格式化成 "12.3%" 塞进 JSON,客户端解析炸了)。
"""

from __future__ import annotations

import datetime as _dt
from decimal import Decimal, InvalidOperation

from vela.config.clocks import format_local


def _as_decimal(value) -> Decimal:
    """Decimal/int/float/str 都收。float 走 str 是防二进制尾巴。"""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"不是可格式化的数值: {value!r}") from None


def render_value(value, fmt: str = "str") -> str:
    if value is None:
        return ""
    if fmt == "int":
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return str(value)  # 脏值原样透出,别吞
    if fmt == "money":
        return f"{_as_decimal(value):.2f}"
    if fmt == "pct":
        # 约定入参是 0~1 的小数;0.123 -> "12.3%"
        return f"{_as_decimal(value) * 100:.1f}%"
    if fmt == "dt":
        if isinstance(value, _dt.datetime):
            return format_local(value)
        if isinstance(value, _dt.date):
            return value.strftime("%Y-%m-%d")
        return str(value)
    return str(value)

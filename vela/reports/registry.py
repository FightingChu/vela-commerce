"""报表注册表。

约定和 vela.jobs.registry 同款:每个 builder 文件顶层
@register_report 挂名,reports/__init__.py 负责全量 import。
行数截断统一收在 build_report,builder 不用管 max_export_rows。
"""

from __future__ import annotations

from typing import Callable

from vela.config.errors import NotFoundError
from vela.config.logging import get_logger
from vela.config.settings import get_settings
from vela.reports.columns import ReportResult

log = get_logger(__name__)

_BUILDERS: dict[str, Callable] = {}


def register_report(name: str) -> Callable[[Callable], Callable]:
    """把 builder 登记为名为 name 的报表。

    builder 返回 ReportResult(columns, rows),rows 的 value 保持
    原始类型(Decimal/datetime),格式化交给导出层。
    """

    def decorator(fn: Callable) -> Callable:
        if name in _BUILDERS:
            raise ValueError(f"报表名字重复注册: {name}")
        fn.report_name = name
        _BUILDERS[name] = fn
        return fn

    return decorator


def list_reports() -> list[str]:
    return sorted(_BUILDERS)


def get_builder(name: str) -> Callable:
    builder = _BUILDERS.get(name)
    if builder is None:
        raise NotFoundError(f"未知报表: {name},已注册: {sorted(_BUILDERS)}")
    return builder


def build_report(name: str, **params) -> ReportResult:
    """唯一对外入口。行数超 settings.max_export_rows 时截断并打标。"""
    builder = get_builder(name)
    result = builder(**params)
    result.name = result.name or name

    max_rows = get_settings().max_export_rows
    if len(result.rows) > max_rows:
        log.warning("report_rows_truncated", report=name,
                    rows=len(result.rows), max_rows=max_rows)
        result.rows = result.rows[:max_rows]
        result.truncated = True
    return result

"""报表导出 csv。逐行渲染逐行写,别把 rendered_rows 整个攒在内存。

Excel 打开中文乱码是 2023 年的十大工单来源,utf-8-sig 的 BOM 别删。
单元格超 EXPORT_CELL_MAX_CHARS 截断加 "...[truncated]" 标记:
历史上一个 reason 字段塞了整篇投诉文,Excel 单元格上限直接爆掉。
"""

from __future__ import annotations

import csv
import os
from typing import IO

from vela.config.constants import EXPORT_CELL_MAX_CHARS
from vela.reports.columns import ReportResult
from vela.reports.formatters import render_value

_TRUNCATED_SUFFIX = "...[truncated]"


def clip_cell(text: str, limit: int = EXPORT_CELL_MAX_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + _TRUNCATED_SUFFIX


def write_csv(result: ReportResult, dest, *, encoding: str = "utf-8-sig") -> int:
    """dest 传路径或已打开的文本句柄都行。返回写出的数据行数(不含表头)。

    result.truncated 时在文件末尾补一行 # 注释打标,Excel 会忽略,
    脚本拿到也知道不完整。
    """
    if isinstance(dest, (str, os.PathLike)):
        with open(dest, "w", newline="", encoding=encoding) as fp:
            return _write(result, fp)
    return _write(result, dest)


def _write(result: ReportResult, fp: IO) -> int:
    writer = csv.writer(fp)
    writer.writerow(result.headers())
    n = 0
    for row in result.rows:
        cells = [
            clip_cell(render_value(row.get(c.key), c.fmt))
            for c in result.columns
        ]
        writer.writerow(cells)
        n += 1
    if result.truncated:
        fp.write(f"# truncated: 行数超上限,仅导出前 {n} 行 (report={result.name})\n")
    return n

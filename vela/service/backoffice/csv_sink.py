"""csv 导出落盘。统一表头、单元格截断、行计数,给 backoffice 的
export_* 用。

encoding 默认 utf-8 带 BOM?不带——财务的 WPS 老版本反而认不出,
2025-08 撕过一轮,结论是业务方自己用 iconv 转。
"""

from __future__ import annotations

import csv
import typing

from vela.config.constants import EXPORT_CELL_MAX_CHARS
from vela.config.errors import ValidationError

#: 导出批大小的默认值。settings.reconcile_batch_rows 是对账口径,
#: 导出偏小些,内存富余的老实例也就这样了
DEFAULT_BATCH_ROWS = 1_000


class CsvSink:
    """流式写 CSV。行是 dict,表头第一次 write_row 时落(或构造时给)。

    没做转义层面的花样,stdlib csv 够用;想要 excel 方言让调用方传
    delimiter。超出 EXPORT_CELL_MAX_CHARS 的单元格截断并加标记,
    schema 层的约定,见 constants.py 注释。
    """

    def __init__(
        self,
        path_or_fp,
        *,
        headers: list[str] | None = None,
        encoding: str = "utf-8",
        delimiter: str = ",",
    ):
        self.headers = headers
        self.rows_written = 0
        self._owns_fp = not hasattr(path_or_fp, "write")
        self._fp = (
            open(path_or_fp, "w", newline="", encoding=encoding)  # noqa: SIM115 - close() 在 __exit__/close 里
            if self._owns_fp
            else path_or_fp
        )
        self._writer = csv.DictWriter(
            self._fp,
            fieldnames=headers or [],
            delimiter=delimiter,
            extrasaction="ignore",
        )
        self._header_written = False

    def _ensure_header(self) -> None:
        if not self._header_written and self.headers:
            self._writer.writeheader()
            self._header_written = True

    def write_row(self, row: dict) -> None:
        if self.headers is None:
            # 表头懒声明:第一行定列序,后面行多出的键丢弃
            self.headers = list(row.keys())
            self._writer.fieldnames = self.headers
        self._ensure_header()
        self._writer.writerow({k: self._clip(v) for k, v in row.items()})
        self.rows_written += 1

    def write_rows(self, rows: typing.Iterable[dict]) -> int:
        for row in rows:
            self.write_row(row)
        return self.rows_written

    @staticmethod
    def _clip(value):
        text = "" if value is None else str(value)
        if len(text) > EXPORT_CELL_MAX_CHARS:
            # 截断加标记,对账看到就知道是超长截的,不是丢数据
            return text[:EXPORT_CELL_MAX_CHARS] + "...[clipped]"
        return text

    def close(self) -> None:
        if self._owns_fp:
            self._fp.close()

    def __enter__(self) -> "CsvSink":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def require_path(path) -> str:
    """导出目标路径的最低限度校验。空串/None 在上层已被 tenant_guard
    类的入口拦过,这里是给直接用 CsvSink 的人兜底。"""
    if not path or not isinstance(path, str):
        raise ValidationError(f"导出路径非法: {path!r}")
    return path

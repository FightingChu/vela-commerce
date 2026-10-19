"""列描述。报表元数据统一在这定义,别在 builder 里裸写 dict。

表头一律中文——运营每周直接拿导出文件开周会,英文表头被打回过两次。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vela.reports.formatters import render_value

# 合法格式标记,和 formatters.render_value 的分支一一对应
FMT_KINDS = ("str", "int", "money", "pct", "dt")


@dataclass(frozen=True)
class Column:
    """一列的描述。fmt 决定导出时怎么转 str。"""

    key: str
    header: str
    fmt: str = "str"

    def __post_init__(self) -> None:
        if self.fmt not in FMT_KINDS:
            raise ValueError(f"未知列格式: {self.fmt!r} ({self.key})")


@dataclass
class ReportResult:
    """builder 的统一返回。rows 里的 value 是原始类型(Decimal/datetime),
    转字符串交给 csv_writer 按 Column.fmt 做,别在 builder 里提前格式化——
    API 侧 JSON 输出要原始值,这个坑 #VT-2321 踩过。
    """

    columns: list[Column]
    rows: list[dict] = field(default_factory=list)
    # 行数被 max_export_rows 截断时置 True,导出文件末尾会打标
    truncated: bool = False
    # 报表名,registry 填,builder 不用管
    name: str = ""

    def headers(self) -> list[str]:
        return [c.header for c in self.columns]

    def rendered_rows(self) -> list[list[str]]:
        """按列定义格式化成字符串行,csv 直接用。"""
        out = []
        for row in self.rows:
            out.append(
                [render_value(row.get(c.key), c.fmt) for c in self.columns]
            )
        return out

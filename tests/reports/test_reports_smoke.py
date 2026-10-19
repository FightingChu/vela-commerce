"""reports 冒烟:注册表齐、period 解析、csv 落盘与截断。

builder 的 SQL 不在这里测——冒烟只保证装配和导出管线是通的,
查询口径各域自己的测试管。
"""

from __future__ import annotations

import csv

import pytest

import vela.reports
from vela.config.constants import EXPORT_CELL_MAX_CHARS
from vela.config.errors import NotFoundError, ValidationError
from vela.reports import build_report, register_report
from vela.reports.columns import Column, ReportResult

EXPECTED_REPORTS = frozenset(
    {
        "sales_daily",
        "order_funnel",
        "refund_summary",
        "inventory_snapshot",
        "coupon_usage",
        "settlement_summary",
        "customer_cohorts",
        "price_change_log",
    }
)


def test_registry_contains_all_reports():
    assert set(vela.reports.list_reports()) == EXPECTED_REPORTS


def test_build_unknown_report_raises_not_found():
    with pytest.raises(NotFoundError):
        build_report("no_such_report")


def test_duplicate_registration_rejected():
    with pytest.raises(ValueError):

        @register_report("sales_daily")
        def _dup():  # pragma: no cover
            ...


# ---- period 解析 ----


class TestPeriod:
    def test_day(self):
        start, end = vela.reports.resolve_period("2026-03-08", "day")
        assert start.isoformat() == "2026-03-07T16:00:00+00:00"  # 北京时间零点
        assert (end - start).total_seconds() == 86400

    def test_day_invalid(self):
        with pytest.raises(ValidationError):
            vela.reports.resolve_period("2026/03/08", "day")
        with pytest.raises(ValidationError):
            vela.reports.resolve_period("2026-02-30", "day")

    def test_week_iso_string(self):
        import datetime as dt

        start, end = vela.reports.resolve_period("2026-W02", "week")
        assert (end - start).total_seconds() == 7 * 86400
        # 周一以北京时间计,UTC 里是周日 16:00
        assert start.astimezone(dt.timezone(dt.timedelta(hours=8))).weekday() == 0

    def test_week_by_date_in_week(self):
        start, end = vela.reports.resolve_period("2026-01-07", "week")
        # 2026-01-07 是周三,那周周一是 01-05 北京时间 00:00
        assert start.isoformat() == "2026-01-04T16:00:00+00:00"

    def test_week_invalid(self):
        with pytest.raises(ValidationError):
            vela.reports.resolve_period("2026-W99", "week")

    def test_month(self):
        start, end = vela.reports.resolve_period("2026-02", "month")
        # 2 月 28 天,跨月边界也算准
        assert (end - start).total_seconds() == 28 * 86400

    def test_month_invalid(self):
        with pytest.raises(ValidationError):
            vela.reports.resolve_period("2026-13", "month")
        with pytest.raises(ValidationError):
            vela.reports.resolve_period("2026-01-extra", "month")

    def test_bad_granularity(self):
        with pytest.raises(ValidationError):
            vela.reports.resolve_period("2026-01-01", "quarter")


# ---- csv_writer ----


class TestCsvWriter:
    def _result(self) -> ReportResult:
        return ReportResult(
            columns=[
                Column("code", "券码"),
                Column("note", "备注"),
                Column("amount", "金额", "money"),
            ],
            rows=[
                {"code": "CPN1", "note": "短备注", "amount": 12.5},
                {"code": "CPN2", "note": "x" * (EXPORT_CELL_MAX_CHARS + 10), "amount": None},
            ],
        )

    def test_write_to_path(self, tmp_path):
        target = tmp_path / "out.csv"
        n = vela.reports.write_csv(self._result(), str(target))
        assert n == 2
        text = target.read_text(encoding="utf-8-sig")
        lines = text.splitlines()
        assert lines[0] == "券码,备注,金额"
        assert "CPN1,短备注,12.50" == lines[1]
        # 超长单元格截断加标
        assert "...[truncated]" in lines[2]
        # BOM 在(utf-8-sig 写出)
        assert target.read_bytes()[:3] == b"\xef\xbb\xbf"

    def test_clip_cell_length(self):
        long = "y" * (EXPORT_CELL_MAX_CHARS + 100)
        clipped = vela.reports.clip_cell(long)
        assert len(clipped) == EXPORT_CELL_MAX_CHARS + len("...[truncated]")
        assert clipped.endswith("...[truncated]")
        assert vela.reports.clip_cell("short") == "short"

    def test_no_trailer_when_not_truncated(self, tmp_path):
        target = tmp_path / "ok.csv"
        vela.reports.write_csv(self._result(), str(target))
        text = target.read_text(encoding="utf-8-sig")
        assert "truncated: " not in text

    def test_writer_parseable(self, tmp_path):
        """写出来的东西要能被 csv 读回去,列数一致。"""
        target = tmp_path / "p.csv"
        vela.reports.write_csv(self._result(), str(target))
        with open(target, newline="", encoding="utf-8-sig") as fp:
            rows = list(csv.reader(fp))
        assert all(len(r) == 3 for r in rows)
        assert len(rows) == 3


# ---- build_report 行数截断 ----


class TestBuildReportTruncation:
    def test_rows_truncated_to_max_export_rows(self, monkeypatch):
        monkeypatch.setenv("VELA_MAX_EXPORT_ROWS", "3")
        register_report("_smoke_big")(_big_builder)
        try:
            result = build_report("_smoke_big")
            assert len(result.rows) == 3
            assert result.truncated is True
        finally:
            from vela.reports.registry import _BUILDERS

            _BUILDERS.pop("_smoke_big", None)


def _big_builder(**_kw) -> ReportResult:
    return ReportResult(
        columns=[Column("i", "序号", "int")],
        rows=[{"i": i} for i in range(10)],
    )


# ---- formatters(顺带,导出口径别再漂) ----


class TestFormatters:
    def test_money(self):
        from decimal import Decimal

        from vela.reports.formatters import render_value

        assert render_value(Decimal("12.5"), "money") == "12.50"
        assert render_value(None, "money") == ""

    def test_pct(self):
        from vela.reports.formatters import render_value

        assert render_value(0.123, "pct") == "12.3%"

    def test_dt_none(self):
        from vela.reports.formatters import render_value

        assert render_value(None, "dt") == ""

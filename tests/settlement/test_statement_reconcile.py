"""对账单汇总 + 差异比对。"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from vela.config.errors import ValidationError
from vela.domain.settlement.reconcile import diff_statements, emit_reconciled
from vela.domain.settlement.statement import build_statement, orders_from_batches
from vela.domain.shared import UNAVAILABLE, EventBatch, make_event


def _sale(sn, amount):
    return {"order_sn": sn, "amount": amount, "kind": "SALE"}


def _refund(sn, amount):
    return {"order_sn": sn, "amount": amount, "kind": "REFUND"}


class TestBuildStatement:
    def test_sale_only(self):
        # 10.05 * 0.05 = 0.5025 -> 0.50;10.00 * 0.05 = 0.50
        result = build_statement(
            [_sale("O1", Decimal("10.05")), _sale("O2", Decimal("10.00"))],
            fee_rate=Decimal("0.05"),
        )
        assert result["gross"] == Decimal("20.05")
        assert result["refund_total"] == 0
        assert result["fee"] == Decimal("1.00")
        assert result["net"] == Decimal("19.05")
        assert [line["fee"] for line in result["lines"]] == [
            Decimal("0.50"),
            Decimal("0.50"),
        ]

    def test_refund_fee_is_negative(self):
        result = build_statement(
            [_sale("O1", Decimal("100.00")), _refund("O2", Decimal("40.00"))],
            fee_rate=Decimal("0.02"),
        )
        assert result["gross"] == Decimal("100.00")
        assert result["refund_total"] == Decimal("40.00")
        # 2.00 + (-0.80)
        assert result["fee"] == Decimal("1.20")
        # net = 100 - 40 - 1.20
        assert result["net"] == Decimal("58.80")

    def test_rounding_per_line_half_up(self):
        # 逐行舍入:0.10 * 0.15 = 0.015 -> 0.02(两行 0.04);
        # 先合计再算费是 0.20 * 0.15 = 0.03,口径不同,#VT-2003
        result = build_statement(
            [_sale("O1", Decimal("0.10")), _sale("O2", Decimal("0.10"))],
            fee_rate=Decimal("0.15"),
        )
        assert result["fee"] == Decimal("0.04")

    def test_bad_kind_rejected(self):
        with pytest.raises(ValidationError):
            build_statement(
                [{"order_sn": "O1", "amount": Decimal("1.00"), "kind": "CHARGEBACK"}],
                fee_rate=Decimal("0.01"),
            )

    def test_empty_orders(self):
        result = build_statement([], fee_rate=Decimal("0.01"))
        assert result["gross"] == 0
        assert result["net"] == 0
        assert result["lines"] == []


class TestOrdersFromBatches:
    def test_from_payloads(self):
        batch = EventBatch(
            [
                make_event(
                    "order.paid",
                    {"order_sn": "O1", "amount": "12.30", "kind": "SALE"},
                ),
                make_event(
                    "order.paid",
                    {"order_sn": "O2", "amount": "3.00", "kind": "REFUND"},
                ),
            ],
            source="bus",
        )
        rows = orders_from_batches([batch])
        assert rows == [
            {"order_sn": "O1", "amount": Decimal("12.30"), "kind": "SALE"},
            {"order_sn": "O2", "amount": Decimal("3.00"), "kind": "REFUND"},
        ]

    def test_empty_batches_is_unavailable_path(self):
        # merge_all([]) 返回 UNAVAILABLE,这里同样归 []
        assert orders_from_batches([]) == []

    def test_batches_without_target_type(self):
        batch = EventBatch([make_event("order.created", {"order_sn": "O1"})])
        assert orders_from_batches([batch]) == []

    def test_unavailable_placeholder_never_leaks_out(self):
        # 显式构造:merge 结果是 UNAVAILABLE 占位时也返回 [],不外漏占位 dict
        merged = EventBatch.merge_all([])
        assert merged == UNAVAILABLE
        assert orders_from_batches([]) != UNAVAILABLE


class TestDiffStatements:
    def test_identical(self):
        ours = {"O1": Decimal("10.00"), "O2": Decimal("3.50")}
        assert diff_statements(ours, dict(ours)) == []

    def test_amount_mismatch(self):
        diff = diff_statements(
            {"O1": Decimal("10.00")}, {"O1": Decimal("9.00")}
        )
        assert len(diff) == 1
        row = diff[0]
        assert row["order_sn"] == "O1"
        assert row["expected"] == Decimal("10.00")
        assert row["actual"] == Decimal("9.00")
        # delta = 我方 - 渠道,正数 = 我方多记
        assert row["delta"] == Decimal("1.00")

    def test_one_sided_missing(self):
        diff = diff_statements({"O1": Decimal("10.00"), "O2": Decimal("5.00")}, {"O1": Decimal("10.00")})
        assert [(r["order_sn"], r["delta"]) for r in diff] == [("O2", Decimal("5.00"))]

    def test_emit_reconciled_only_on_diff(self):
        assert emit_reconciled([], "2025-09") is None
        event = emit_reconciled([{"order_sn": "O1"}], "2025-09")
        assert event["type"] == "settlement.reconciled"
        assert event["payload"]["period"] == "2025-09"
        assert event["payload"]["diff_count"] == 1


def test_is_overdue_paths():
    from vela.domain.settlement.terms import due_date, is_overdue

    confirmed = dt.datetime(2025, 9, 1, tzinfo=dt.timezone.utc)
    assert due_date(confirmed) == confirmed + dt.timedelta(days=30)
    assert due_date(confirmed, 7) == confirmed + dt.timedelta(days=7)

    now = dt.datetime(2025, 10, 20, tzinfo=dt.timezone.utc)
    overdue = {"status": "pushed", "due_date": confirmed + dt.timedelta(days=30)}
    assert is_overdue(overdue, now) is True
    # 已结清即使过期也不算逾期
    settled = dict(overdue, status="settled")
    assert is_overdue(settled, now) is False
    # 未到期
    fresh = {"status": "confirmed", "due_date": now + dt.timedelta(days=1)}
    assert is_overdue(fresh, now) is False
    # sqlite 裸 datetime 按 UTC 解释
    naive = {"status": "pushed", "due_date": (now - dt.timedelta(days=1)).replace(tzinfo=None)}
    assert is_overdue(naive, now) is True

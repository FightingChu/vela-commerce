"""backoffice:csv 落盘、任务锁互斥、导出与调整的主干路径。"""

from __future__ import annotations

import datetime as dt
import io
from decimal import Decimal

import pytest

import vela.domain.customer  # noqa: F401
import vela.domain.inventory  # noqa: F401
import vela.domain.order  # noqa: F401
import vela.domain.pricing  # noqa: F401
import vela.domain.promotion  # noqa: F401
import vela.domain.settlement  # noqa: F401

from vela.config.clocks import utc_now
from vela.config.errors import TenantError, ValidationError
from vela.domain.customer import register_customer
from vela.domain.order import DefaultPricer, OrderService
from vela.service.backoffice import (
    CsvSink,
    LockHeldError,
    TaskLock,
    adjust_line_price,
    export_customers,
    export_orders,
    grant_to_customers,
    hold,
)


# ---- csv_sink ----

class TestCsvSink:
    def test_write_and_readback(self, tmp_path):
        path = tmp_path / "orders.csv"
        with CsvSink(str(path), headers=["order_sn", "total"]) as sink:
            sink.write_row({"order_sn": "VL1", "total": "20.00"})
            sink.write_row({"order_sn": "VL2", "total": "7.00"})
            assert sink.rows_written == 2

        text = path.read_text(encoding="utf-8")
        lines = text.strip().splitlines()
        assert lines[0] == "order_sn,total"
        assert lines[1] == "VL1,20.00"
        assert lines[2] == "VL2,7.00"

    def test_long_cell_clipped(self):
        buf = io.StringIO()
        with CsvSink(buf, headers=["note"]) as sink:
            sink.write_row({"note": "x" * 5000})
        # 截断 + 标记,不是静默丢
        assert "x" * 100 in buf.getvalue()
        assert "...[clipped]" in buf.getvalue()

    def test_extra_keys_ignored(self):
        buf = io.StringIO()
        with CsvSink(buf, headers=["a"]) as sink:
            sink.write_row({"a": 1, "b": 2})
        assert buf.getvalue().strip().splitlines()[1] == "1"


# ---- task_lock ----

class FakeClock:
    def __init__(self):
        self.at = utc_now()

    def now(self):
        return self.at

    def advance(self, seconds):
        self.at = self.at + dt.timedelta(seconds=seconds)


class TestTaskLock:
    def test_mutual_exclusion(self):
        lock = TaskLock(ttl_seconds=60, clock=FakeClock())
        assert lock.acquire("export:orders", owner="job-1") is True
        # 第二个人抢不到
        assert lock.acquire("export:orders", owner="job-2") is False
        # 只有持锁人能放
        assert lock.release("export:orders", owner="job-2") is False
        assert lock.release("export:orders", owner="job-1") is True
        # 放了之后能再抢
        assert lock.acquire("export:orders", owner="job-2") is True

    def test_expired_lock_reacquirable(self):
        clock = FakeClock()
        lock = TaskLock(ttl_seconds=60, clock=clock)
        assert lock.acquire("stale", owner="old") is True
        clock.advance(61)  # 过期,可以顶掉
        assert lock.acquire("stale", owner="new") is True
        assert lock.holder("stale") == "new"

    def test_hold_context(self):
        lock = TaskLock(ttl_seconds=60, clock=FakeClock())
        with hold(lock, "adjust", owner="op-1"):
            with pytest.raises(LockHeldError):
                with hold(lock, "adjust", owner="op-2"):
                    pass
        # 正常退出自动放锁
        with hold(lock, "adjust", owner="op-2"):
            pass


# ---- export ----

@pytest.fixture
def some_orders(svc_session):
    service = OrderService(
        svc_session, pricer=DefaultPricer({101: Decimal("10.00")})
    )
    service.create_order(7, [{"sku_id": 101, "qty": 1}], token="bo-1")
    service.create_order(7, [{"sku_id": 101, "qty": 2}])
    svc_session.flush()


def test_export_orders_requires_explicit_tenant(svc_session, some_orders):
    with pytest.raises(TenantError):
        export_orders(svc_session, None, path="/tmp/x.csv")


def test_export_orders_to_sink(svc_session, some_orders):
    buf = io.StringIO()
    sink = CsvSink(buf, headers=[
        "order_sn", "customer_id", "status", "channel",
        "total", "discount", "paid", "created_at",
    ])
    result = export_orders(svc_session, "main", sink=sink)
    assert result["rows"] == 2
    assert result["tenant"] == "main"

    lines = buf.getvalue().strip().splitlines()
    assert len(lines) == 3  # 表头 + 2 行
    assert lines[1].startswith("VL")


def test_export_customers_to_path(svc_session, tmp_path):
    register_customer("ext-1", "小明", phone="13800005678", session=svc_session)
    svc_session.flush()

    path = tmp_path / "customers.csv"
    result = export_customers(svc_session, "main", path=str(path))
    assert result["rows"] == 1

    text = path.read_text(encoding="utf-8")
    assert "ext-1" in text
    assert "138****5678" in text  # 出去的就是脱敏串


# ---- order_adjust / coupon_grant(主干的冒烟) ----

def test_adjust_line_price_recomputes_total(svc_session):
    service = OrderService(
        svc_session, pricer=DefaultPricer({101: Decimal("10.00")})
    )
    agg = service.create_order(7, [{"sku_id": 101, "qty": 3}])
    svc_session.flush()

    line_id = agg.lines[0].id
    adjusted = adjust_line_price(
        svc_session, agg.model.order_sn, line_id, "8.00",
        reason="客服补偿", operator="op-9",
    )
    assert adjusted.model.total_amount == Decimal("24.00")
    assert adjusted.lines[0].unit_price == Decimal("8.00")


def test_grant_to_customers_creates_child_coupons(svc_session):
    from vela.service.coupon_admin import create_coupon

    create_coupon(
        svc_session, code="M100", title="满100减20", kind="THRESHOLD",
        total_quota=100, threshold_amount="100", discount_amount="20",
        operator="op-1",
    )
    codes = grant_to_customers(svc_session, "M100", [1, 2, 3], operator="op-1")
    assert len(codes) == 3
    assert all(code.startswith("M100-G") for code in codes)

    # 名单为空直接拦
    with pytest.raises(ValidationError):
        grant_to_customers(svc_session, "M100", [], operator="op-1")

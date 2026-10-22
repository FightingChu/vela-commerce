"""DTO 边界。校验规则是 HTTP 层的合同,改动要过测试。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vela.api.schemas import (
    AddressIn,
    CreateOrderRequest,
    HealthStatus,
    OrderLineIn,
    PageMeta,
    ReconcileRunIn,
    RefundRequest,
    TenantIn,
    TraceHeaders,
)


def test_order_line_rejects_zero_qty():
    with pytest.raises(ValidationError):
        OrderLineIn(sku_id=1, qty=0)
    with pytest.raises(ValidationError):
        OrderLineIn(sku_id=0, qty=1)


def test_create_order_requires_lines():
    ok = CreateOrderRequest(customer_id=1, lines=[{"sku_id": 1, "qty": 1}])
    assert ok.lines[0].sku_id == 1
    assert ok.channel == "app"  # 缺省渠道
    with pytest.raises(ValidationError):
        CreateOrderRequest(customer_id=1, lines=[])


def test_create_order_forbids_extra_fields():
    with pytest.raises(ValidationError):
        CreateOrderRequest(customer_id=1, lines=[{"sku_id": 1, "qty": 1}], hack="x")


def test_refund_amount_must_be_decimal_string():
    ok = RefundRequest(order_sn="VL1", amount="12.34", reason="质量问题")
    assert ok.amount == "12.34"
    for bad in ("abc", "-1", ""):
        with pytest.raises(ValidationError):
            RefundRequest(order_sn="VL1", amount=bad, reason="质量问题")


def test_tenant_in_length_limit():
    with pytest.raises(ValidationError):
        TenantIn(tenant_id="x" * 33, name="超长租户")
    ok = TenantIn(tenant_id="shop-a", name="A 店", plan="PRO")
    assert ok.plan == "PRO"
    with pytest.raises(ValidationError):
        TenantIn(tenant_id="shop-a", name="A 店", plan="ULTIMATE")


def test_address_in_defaults():
    addr = AddressIn(
        receiver="张三", phone="13800000000",
        province="浙江", city="杭州", detail="文一西路 1 号",
    )
    assert addr.is_default is False
    assert addr.district is None
    with pytest.raises(ValidationError):
        AddressIn(receiver="张三", phone="13800000000",
                  province="浙江", city="杭州", detail="")


def test_page_meta_boundaries():
    page = PageMeta(total=100, offset=90, limit=20)
    assert page.has_next is False
    assert PageMeta(total=100, offset=0, limit=20).has_next is True
    with pytest.raises(ValidationError):
        PageMeta(total=-1, offset=0, limit=20)
    with pytest.raises(ValidationError):
        PageMeta(total=0, offset=0, limit=0)


def test_trace_headers_alias():
    headers = TraceHeaders.model_validate(
        {"X-Vela-Trace-Id": "t-1", "X-Vela-Tenant": "shop-a"}
    )
    assert headers.trace_id == "t-1"
    assert headers.tenant_id == "shop-a"
    # 只带 trace 也行,租户可缺
    assert TraceHeaders.model_validate({"X-Vela-Trace-Id": "t-2"}).tenant_id is None


def test_health_status_literal():
    assert HealthStatus(status="ok", db=True, bus=True).status == "ok"
    with pytest.raises(ValidationError):
        HealthStatus(status="green", db=True, bus=True)


def test_reconcile_run_in_defaults():
    run = ReconcileRunIn()
    assert run.warehouse == "MAIN"
    assert run.dry_run is True
    assert run.expected is None

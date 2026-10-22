"""订单查询契约:单查/分页/软删口径。"""

from __future__ import annotations

from decimal import Decimal

import pytest

import vela.domain.customer
import vela.domain.inventory
import vela.domain.order
import vela.domain.pricing
import vela.domain.promotion
import vela.domain.settlement  # noqa: F401
from vela.domain.order import DefaultPricer, OrderRepository, OrderService
from vela.service.order_query import get_order_view, list_customer_orders

PRICER = DefaultPricer({101: Decimal("10.00"), 102: Decimal("3.50")})


@pytest.fixture
def orders(svc_session):
    """客户 7 两单、客户 8 一单。返回单号列表(客户 7 的,新单在前)。"""
    service = OrderService(svc_session, pricer=PRICER)
    sn1 = service.create_order(7, [{"sku_id": 101, "qty": 1}], token="q-1").model.order_sn
    sn2 = service.create_order(7, [{"sku_id": 102, "qty": 2}]).model.order_sn
    sn3 = service.create_order(8, [{"sku_id": 101, "qty": 1}]).model.order_sn
    svc_session.flush()
    return sn1, sn2, sn3


def test_get_order_view(orders, svc_session):
    _sn1, sn2, _ = orders
    view = get_order_view(sn2)

    assert view is not None
    assert view["order_sn"] == sn2
    assert view["customer_id"] == 7
    assert view["status"] == "created"
    # 3.50 * 2
    assert view["total"] == "7.00"
    assert view["discount"] == "0.00"
    assert len(view["lines"]) == 1
    assert view["lines"][0]["unit_price"] == "3.50"


def test_get_order_view_missing_returns_none(orders):
    assert get_order_view("VL999999999999") is None


def test_list_customer_orders(orders, svc_session):
    sn1, sn2, _ = orders

    page = list_customer_orders(7)
    assert page["total"] == 2
    assert [item["order_sn"] for item in page["items"]] == [sn2, sn1]  # 新单在前
    assert page["offset"] == 0
    assert page["limit"] > 0  # settings 默认页大小

    # 客户 8 看不到客户 7 的单
    assert list_customer_orders(8)["total"] == 1


def test_list_customer_orders_paging(orders):
    page = list_customer_orders(7, offset=0, limit=1)
    assert page["total"] == 2
    assert len(page["items"]) == 1

    page2 = list_customer_orders(7, offset=1, limit=1)
    assert len(page2["items"]) == 1
    assert page2["items"][0]["order_sn"] != page["items"][0]["order_sn"]

    # 翻出界了,items 空但 total 不变
    page3 = list_customer_orders(7, offset=5, limit=10)
    assert page3["items"] == []
    assert page3["total"] == 2


def test_list_ignores_soft_deleted(orders, svc_session):
    sn1, _, _ = orders
    model = OrderRepository(svc_session).get_by_sn(sn1)
    model.soft_delete()
    svc_session.flush()

    assert get_order_view(sn1) is None
    assert list_customer_orders(7)["total"] == 1

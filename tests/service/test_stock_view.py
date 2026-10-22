"""库存视图契约:字段形状/缺行兜底/预占反映。"""

from __future__ import annotations

import vela.domain.customer
import vela.domain.inventory
import vela.domain.order
import vela.domain.pricing
import vela.domain.promotion
import vela.domain.settlement  # noqa: F401
from vela.service.inventory_ops import stock_view


def test_stock_view_shape(svc_session, seed_stock):
    seed_stock(201, on_hand=50)

    view = stock_view(201)
    assert view == {
        "sku_id": 201,
        "warehouse": "MAIN",
        "on_hand": 50,
        "reserved": 0,
        "available": 50,
    }


def test_stock_view_missing_row_is_zero(svc_session):
    """没初始化过库存返回全 0,不抛不建行。"""
    view = stock_view(999)
    assert view == {
        "sku_id": 999,
        "warehouse": "MAIN",
        "on_hand": 0,
        "reserved": 0,
        "available": 0,
    }
    # 确认真的没插行
    assert stock_view(999)["on_hand"] == 0


def test_stock_view_warehouse_isolated(svc_session, seed_stock):
    seed_stock(202, on_hand=10, warehouse="MAIN")
    seed_stock(202, on_hand=7, warehouse="EAST")

    assert stock_view(202)["on_hand"] == 10
    assert stock_view(202, warehouse="EAST")["on_hand"] == 7
    # 没这个仓的行,照样全 0
    assert stock_view(202, warehouse="WEST")["available"] == 0


def test_stock_view_reflects_reservation(svc_session, seed_price, seed_stock):
    """下单预占之后,视图的 reserved/available 要跟着动。"""
    seed_price(203, "1.00")
    seed_stock(203, on_hand=10)

    from vela.service.checkout import create_checkout

    result = create_checkout(7, [{"sku_id": 203, "qty": 4}])
    assert result["reservations"]

    view = stock_view(203)
    assert view["reserved"] == 4
    assert view["available"] == 6
    assert view["on_hand"] == 10  # 预占不动在途,扣减发生在消费时

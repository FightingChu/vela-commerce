"""下单编排:金额/单号/预占 + 幂等冲突 + 缺价与缺货。"""

from __future__ import annotations

import pytest

import vela.domain.customer  # noqa: F401 - 建表前注册全部模型
import vela.domain.inventory  # noqa: F401
import vela.domain.order  # noqa: F401
import vela.domain.pricing  # noqa: F401
import vela.domain.promotion  # noqa: F401
import vela.domain.settlement  # noqa: F401

from vela.config.constants import ORDER_SN_PREFIX
from vela.config.errors import ValidationError
from vela.db.tenant import tenant_context
from vela.domain.inventory import InventoryShortageError
from vela.domain.inventory.stock_repo import StockRepository
from vela.domain.order import DuplicateOrderError, OrderRepository
from vela.service.checkout import create_checkout


def test_create_checkout_ok(svc_session, seed_price, seed_stock):
    seed_price(101, "10.00")
    seed_stock(101, on_hand=100)

    result = create_checkout(
        7,
        [{"sku_id": 101, "qty": 2}],
        channel="app",
        token="tok-1",
    )

    # 单号/金额
    assert result["order_sn"].startswith(ORDER_SN_PREFIX)
    assert result["total"] == "20.00"
    assert result["discount"] == "0.00"

    # 行快照:单价/行金额/预占凭证
    assert len(result["lines"]) == 1
    line = result["lines"][0]
    assert line["sku_id"] == 101
    assert line["qty"] == 2
    assert line["unit_price"] == "10.00"
    assert line["line_amount"] == "20.00"
    assert isinstance(line["reservation_ref"], int)

    assert result["reservations"] == [line["reservation_ref"]]

    # 库存侧:预占真的挂上了
    stock = StockRepository(svc_session).get_or_create(101, "MAIN")
    assert stock.reserved == 2
    assert stock.available == 98

    # 订单落库,remark 里有幂等标记
    model = OrderRepository(svc_session).get_by_sn(result["order_sn"])
    assert model.status == "created"
    assert "idem:order_create:tok-1" in (model.remark or "")


def test_create_checkout_token_conflict(svc_session, seed_price, seed_stock):
    seed_price(101, "5.50")
    seed_stock(101)

    first = create_checkout(7, [{"sku_id": 101, "qty": 1}], token="tok-dup")
    with pytest.raises(DuplicateOrderError):
        create_checkout(7, [{"sku_id": 101, "qty": 1}], token="tok-dup")

    # 幂等命中不代表首次失败,首单还在
    assert OrderRepository(svc_session).get_by_sn(first["order_sn"]) is not None

    # 老网关占位 token("-1")归一化成空,不拦截
    second = create_checkout(7, [{"sku_id": 101, "qty": 1}], token="-1")
    assert second["order_sn"] != first["order_sn"]


def test_create_checkout_missing_price_rejected(svc_session, seed_stock):
    seed_stock(102)
    with pytest.raises(ValidationError, match="缺价"):
        create_checkout(7, [{"sku_id": 102, "qty": 1}])


def test_create_checkout_shortage(svc_session, seed_price, seed_stock):
    seed_price(101, "10.00")
    seed_stock(101, on_hand=1)
    with pytest.raises(InventoryShortageError):
        create_checkout(7, [{"sku_id": 101, "qty": 5}])


def test_create_checkout_tenant_context(svc_session, seed_price, seed_stock):
    """显式租户下单:数据按租户隔离,单据落到对应租户。

    tenant_id 列的 ORM default 恒为 main,所以种子和断言都要显式带租户。
    """
    seed_price(101, "3.00", tenant="tenant-a")
    seed_stock(101, tenant="tenant-a")

    result = create_checkout(
        9, [{"sku_id": 101, "qty": 1}], tenant="tenant-a", trace="t-abc"
    )
    # 单据落在 tenant-a,断言也要在对应租户上下文里查
    with tenant_context("tenant-a"):
        model = OrderRepository(svc_session).get_by_sn(result["order_sn"])
    assert model.tenant_id == "tenant-a"
    assert result["total"] == "3.00"

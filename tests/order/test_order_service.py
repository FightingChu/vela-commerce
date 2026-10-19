"""下单服务:创建 / 幂等冲突 / 查询 / 合计。"""

from __future__ import annotations

from decimal import Decimal

import pytest

import vela.domain.order  # noqa: F401 - 注册模型建表
from vela.config.errors import ValidationError
from vela.domain.order import DefaultPricer, DuplicateOrderError, OrderService


class FakeReserver:
    """递增 int 当预占凭证,和库存域的真实返回形状一致。"""

    def __init__(self):
        self.calls = []
        self._next = 100

    def __call__(self, sku_id, qty, order_sn):
        self.calls.append((sku_id, qty, order_sn))
        self._next += 1
        return self._next


@pytest.fixture
def reserver():
    return FakeReserver()


@pytest.fixture
def service(db_session, reserver):
    pricer = DefaultPricer({101: Decimal("10.00"), 102: Decimal("3.50")})
    return OrderService(db_session, reserver=reserver, pricer=pricer)


def test_create_order_total_and_lines(service, reserver):
    agg = service.create_order(
        7,
        [{"sku_id": 101, "qty": 2}, {"sku_id": 102, "qty": 3}],
        token="tok-1",
    )
    assert len(agg.lines) == 2
    # 10.00 * 2 + 3.50 * 3
    assert agg.model.total_amount == Decimal("30.50")
    assert agg.model.discount_amount == 0
    assert agg.model.status == "created"

    # 预占按行调用,凭证落在快照里
    assert [(c[0], c[1]) for c in reserver.calls] == [(101, 2), (102, 3)]
    refs = [line.snapshot["reservation_ref"] for line in agg.lines]
    assert refs == [101, 102]

    assert [e["type"] for e in agg.events] == ["order.created"]
    assert agg.events[0]["payload"]["order_sn"] == agg.model.order_sn


def test_get_order_roundtrip(service):
    created = service.create_order(7, [{"sku_id": 101, "qty": 1}], token="tok-2")
    loaded = service.get_order(created.model.order_sn)
    assert loaded.model.order_sn == created.model.order_sn
    assert loaded.model.total_amount == Decimal("10.00")
    assert len(loaded.lines) == 1
    assert loaded.lines[0].snapshot["sku_id"] == 101


def test_idempotent_token_conflict(service):
    first = service.create_order(7, [{"sku_id": 101, "qty": 1}], token="dup-tok")
    with pytest.raises(DuplicateOrderError) as exc:
        service.create_order(7, [{"sku_id": 102, "qty": 1}], token="dup-tok")
    # detail 带已存在单的 order_sn,网关靠它回查
    assert exc.value.detail["order_sn"] == first.model.order_sn

    # 不同 token 不冲突
    other = service.create_order(7, [{"sku_id": 101, "qty": 1}], token="tok-3")
    assert other.model.order_sn != first.model.order_sn


def test_no_token_no_idempotency(service):
    a = service.create_order(7, [{"sku_id": 101, "qty": 1}])
    b = service.create_order(7, [{"sku_id": 101, "qty": 1}])
    assert a.model.order_sn != b.model.order_sn


def test_missing_price_rejected(service):
    with pytest.raises(ValidationError) as exc:
        service.create_order(7, [{"sku_id": 999, "qty": 1}])
    assert 999 in exc.value.detail.get("missing_skus", [])


def test_line_payload_validation(service):
    with pytest.raises(ValidationError):
        service.create_order(7, [])
    with pytest.raises(ValidationError):
        service.create_order(7, [{"sku_id": 101, "qty": 0}])
    with pytest.raises(ValidationError):
        service.create_order(7, [{"qty": 1}])


def test_explicit_unit_price_skips_pricer(db_session):
    # 行里带价就不问 pricer(老网关的合约价路径)
    svc = OrderService(db_session)  # 连 pricer 都没有
    agg = svc.create_order(7, [{"sku_id": 101, "qty": 2, "unit_price": "4.25"}])
    assert agg.model.total_amount == Decimal("8.50")
    assert agg.lines[0].snapshot.get("reservation_ref") is None  # 也没注入 reserver

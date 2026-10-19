"""退款:幂等 / 超付 / 状态推进。"""

from __future__ import annotations

from decimal import Decimal

import pytest

import vela.domain.order  # noqa: F401 - 注册模型建表
from vela.config.errors import ValidationError
from vela.domain.order import (
    DefaultPricer,
    DuplicateOrderError,
    OrderService,
    OrderStateError,
    approve_refund,
    mark_refund_done,
    request_refund,
)


@pytest.fixture
def paid_order(db_session):
    svc = OrderService(
        db_session, pricer=DefaultPricer({101: Decimal("10.00")})
    )
    agg = svc.create_order(7, [{"sku_id": 101, "qty": 2}], token="pay-1")  # 20.00
    agg.mark_paid()
    db_session.flush()
    return agg


class TestRequestRefund:
    def test_happy_path(self, db_session, paid_order):
        refund = request_refund(
            db_session, paid_order.model.order_sn, "5.00", "少发了一件", token="rf-1"
        )
        assert refund.status == "pending"
        assert refund.amount == Decimal("5.00")
        assert refund.applied_at is not None
        assert refund.done_at is None

        # 订单推进到 REFUNDING
        reloaded = OrderService(db_session).get_order(paid_order.model.order_sn)
        assert reloaded.model.status == "refunding"
        assert refund.events[0]["type"] == "order.refund_requested"
        assert refund.events[0]["payload"]["refund_sn"] == refund.refund_sn

    def test_idempotent_token(self, db_session, paid_order):
        request_refund(db_session, paid_order.model.order_sn, "5.00", "r", token="rf-dup")
        with pytest.raises(DuplicateOrderError) as exc:
            request_refund(db_session, paid_order.model.order_sn, "5.00", "r", token="rf-dup")
        assert exc.value.detail["order_sn"] == paid_order.model.order_sn

    def test_over_paid_amount_rejected(self, db_session, paid_order):
        with pytest.raises(ValidationError) as exc:
            request_refund(db_session, paid_order.model.order_sn, "20.01", "贪心")
        assert exc.value.detail["paid_amount"] == str(Decimal("20.00"))

    def test_full_refund_allowed(self, db_session, paid_order):
        refund = request_refund(db_session, paid_order.model.order_sn, "20.00", "整单退")
        assert refund.amount == Decimal("20.00")

    def test_unpaid_order_rejected(self, db_session):
        svc = OrderService(db_session, pricer=DefaultPricer({101: Decimal("10.00")}))
        agg = svc.create_order(7, [{"sku_id": 101, "qty": 1}])
        with pytest.raises(OrderStateError):
            request_refund(db_session, agg.model.order_sn, "1.00", "没付就想退")

    def test_nonpositive_amount_rejected(self, db_session, paid_order):
        with pytest.raises(ValidationError):
            request_refund(db_session, paid_order.model.order_sn, "0", "x")
        with pytest.raises(ValidationError):
            request_refund(db_session, paid_order.model.order_sn, "-5", "x")


class TestRefundLifecycle:
    def test_pending_to_done(self, db_session, paid_order):
        refund = request_refund(db_session, paid_order.model.order_sn, "5.00", "r")
        approve_refund(db_session, refund.refund_sn)
        assert refund.status == "approved"
        done = mark_refund_done(db_session, refund.refund_sn)
        assert done.status == "done"
        assert done.done_at is not None

        # 订单一并推到 REFUNDED
        reloaded = OrderService(db_session).get_order(paid_order.model.order_sn)
        assert reloaded.model.status == "refunded"
        assert done.events[0]["type"] == "order.refunded"

    def test_skip_approve_rejected(self, db_session, paid_order):
        refund = request_refund(db_session, paid_order.model.order_sn, "5.00", "r")
        with pytest.raises(OrderStateError):
            mark_refund_done(db_session, refund.refund_sn)

    def test_double_approve_rejected(self, db_session, paid_order):
        refund = request_refund(db_session, paid_order.model.order_sn, "5.00", "r")
        approve_refund(db_session, refund.refund_sn)
        with pytest.raises(OrderStateError):
            approve_refund(db_session, refund.refund_sn)

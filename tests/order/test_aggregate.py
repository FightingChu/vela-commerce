"""聚合:合计 / 优惠分摊 / 状态判断。内存构造,不落库。"""

from __future__ import annotations

from decimal import Decimal

import pytest

import vela.domain.order  # noqa: F401 - 注册模型建表
from vela.config.errors import ValidationError
from vela.domain.order import Order, OrderStateError, OrderStatus
from vela.domain.order.models import OrderLineModel, OrderModel


def make_order(line_amounts, discount_shares=None):
    # status 要显式给:列 default 只在 flush 时生效,内存对象上是 None
    model = OrderModel(order_sn="VL260101000001", customer_id=1, status="created")
    for i, amount in enumerate(line_amounts):
        model.lines.append(
            OrderLineModel(
                sku_id=100 + i,
                qty=1,
                unit_price=amount,
                line_amount=Decimal(amount),
                discount_share=Decimal((discount_shares or [Decimal(0)] * len(line_amounts))[i]),
            )
        )
    return Order(model)


class TestRecomputeTotal:
    def test_sum_lines(self):
        agg = make_order(["20.00", "30.00", "50.00"])
        assert agg.recompute_total() == Decimal("100.00")
        assert agg.model.total_amount == Decimal("100.00")

    def test_minus_discount_shares(self):
        agg = make_order(["20.00", "30.00"], discount_shares=["2.00", "3.00"])
        assert agg.recompute_total() == Decimal("45.00")
        assert agg.model.discount_amount == Decimal("5.00")

    def test_discount_exceeds_gross_rejected(self):
        agg = make_order(["10.00"], discount_shares=["10.01"])
        with pytest.raises(ValidationError):
            agg.recompute_total()

    def test_empty_order_rejected(self):
        with pytest.raises(ValidationError):
            make_order([]).recompute_total()


class TestAllocateDiscount:
    def test_default_weights_by_line_amount(self):
        agg = make_order(["20.00", "30.00", "50.00"])
        parts = agg.allocate_discount(Decimal("12.00"))
        # 12 * [20,30,50]/100 -> 2.40, 3.60, 余数 6.00 给最后一份
        assert parts == [Decimal("2.40"), Decimal("3.60"), Decimal("6.00")]
        assert sum(parts) == Decimal("12.00")
        assert agg.model.discount_amount == Decimal("12.00")
        assert agg.model.total_amount == Decimal("88.00")

    def test_allocation_sum_strictly_equal_when_not_divisible(self):
        # 10.00 / 3 除不尽,余数全给最后一份,合计必须严格相等
        agg = make_order(["33.33", "33.33", "33.34"])
        parts = agg.allocate_discount(Decimal("10.00"))
        shares = [line.discount_share for line in agg.lines]
        assert sum(shares) == Decimal("10.00")
        assert sum(parts) == Decimal("10.00")
        assert agg.recompute_total() == Decimal("90.00")

    def test_custom_weights(self):
        agg = make_order(["20.00", "30.00"])
        parts = agg.allocate_discount(Decimal("10.00"), weights=[Decimal(3), Decimal(2)])
        assert parts[0] == Decimal("6.00")
        assert parts[1] == Decimal("4.00")

    def test_zero_discount(self):
        agg = make_order(["10.00", "20.00"])
        parts = agg.allocate_discount(Decimal(0))
        assert sum(parts) == 0
        assert agg.model.total_amount == Decimal("30.00")

    def test_negative_discount_rejected(self):
        agg = make_order(["10.00"])
        with pytest.raises(ValidationError):
            agg.allocate_discount(Decimal(-1))

    def test_weight_count_mismatch_rejected(self):
        agg = make_order(["10.00", "20.00"])
        with pytest.raises(ValidationError):
            agg.allocate_discount(Decimal(1), weights=[1])


class TestStatusJudgement:
    def test_can_cancel(self):
        assert make_order(["10.00"]).can_cancel() is True
        paid = make_order(["10.00"])
        paid.model.order_status = OrderStatus.PAID
        assert paid.can_cancel() is False
        cancelled = make_order(["10.00"])
        cancelled.model.order_status = OrderStatus.CANCELLED
        assert cancelled.can_cancel() is False

    def test_can_refund(self):
        for status in (OrderStatus.PAID, OrderStatus.PARTIAL_SHIPPED, OrderStatus.SHIPPED):
            agg = make_order(["10.00"])
            agg.model.order_status = status
            assert agg.can_refund() is True, status
        for status in (OrderStatus.CREATED, OrderStatus.CANCELLED, OrderStatus.REFUNDING, OrderStatus.COMPLETED):
            agg = make_order(["10.00"])
            agg.model.order_status = status
            assert agg.can_refund() is False, status


class TestMarkPaid:
    def test_from_created(self):
        agg = make_order(["10.00", "20.00"])
        agg.recompute_total()
        agg.mark_paid()
        assert agg.model.order_status is OrderStatus.PAID
        assert agg.model.paid_amount == Decimal("30.00")
        assert agg.model.paid_at is not None

    def test_from_cancelled_rejected(self):
        agg = make_order(["10.00"])
        agg.model.order_status = OrderStatus.CANCELLED
        with pytest.raises(OrderStateError):
            agg.mark_paid()

    def test_refund_rejected_edge_is_not_pay(self):
        # REFUNDING -> PAID 是退款驳回,不是支付,mark_paid 要拦
        agg = make_order(["10.00"])
        agg.model.order_status = OrderStatus.REFUNDING
        with pytest.raises((OrderStateError, ValidationError)):
            agg.mark_paid()

"""取消 + 拆单。金额守恒是硬要求,对账拿这个对。"""

from __future__ import annotations

from decimal import Decimal

import pytest

import vela.domain.order  # noqa: F401 - 注册模型建表
from vela.config.errors import ValidationError
from vela.domain.order import (
    DefaultPricer,
    OrderService,
    OrderStateError,
    cancel_order,
    split_order,
)
from vela.domain.order.repository import OrderRepository


def make_service(db_session):
    reserver = lambda sku_id, qty, sn: sku_id * 1000 + qty  # noqa: E731 - 测试桩
    pricer = DefaultPricer(
        {101: Decimal("20.00"), 102: Decimal("30.00"), 103: Decimal("50.00")}
    )
    return OrderService(db_session, reserver=reserver, pricer=pricer)


class TestCancel:
    def test_cancel_created(self, db_session):
        svc = make_service(db_session)
        agg = svc.create_order(7, [{"sku_id": 101, "qty": 1}, {"sku_id": 102, "qty": 1}])

        released = []

        def release_fn(ref, order_sn):
            released.append((ref, order_sn))

        cancelled = cancel_order(db_session, agg.model.order_sn, reason="用户手滑", release_fn=release_fn)

        assert cancelled.model.status == "cancelled"
        assert "cancelled:用户手滑" in cancelled.model.remark
        assert [l.line_status for l in cancelled.lines] == ["cancelled", "cancelled"]
        # 预占凭证原样还给库存侧(sku_id * 1000 + qty)
        assert released == [(101001, agg.model.order_sn), (102001, agg.model.order_sn)]
        assert [e["type"] for e in cancelled.events] == ["order.cancelled"]

    def test_cancel_without_release_fn_only_flips_status(self, db_session):
        svc = make_service(db_session)
        agg = svc.create_order(7, [{"sku_id": 101, "qty": 1}])
        cancelled = cancel_order(db_session, agg.model.order_sn, reason="超时")
        assert cancelled.model.status == "cancelled"

    def test_cancel_paid_rejected(self, db_session):
        svc = make_service(db_session)
        agg = svc.create_order(7, [{"sku_id": 101, "qty": 1}])
        agg.mark_paid()
        db_session.flush()
        with pytest.raises(OrderStateError):
            cancel_order(db_session, agg.model.order_sn, reason="想白嫖")

    def test_cancel_twice_rejected(self, db_session):
        svc = make_service(db_session)
        agg = svc.create_order(7, [{"sku_id": 101, "qty": 1}])
        cancel_order(db_session, agg.model.order_sn, reason="first")
        with pytest.raises(OrderStateError):
            cancel_order(db_session, agg.model.order_sn, reason="again")


class TestSplit:
    def test_split_conserves_amounts(self, db_session):
        svc = make_service(db_session)
        agg = svc.create_order(
            7, [{"sku_id": 101, "qty": 1}, {"sku_id": 102, "qty": 1}, {"sku_id": 103, "qty": 1}]
        )
        original_total = agg.model.total_amount  # 100.00
        agg.allocate_discount(Decimal("12.00"))  # 行摊 2.40 / 3.60 / 6.00
        db_session.flush()
        discounted_total = agg.model.total_amount  # 88.00
        parent_sn = agg.model.order_sn

        parent, child = split_order(db_session, parent_sn, [0, 2])

        # 金额守恒:父 + 子 == 原合计
        assert parent.model.total_amount + child.model.total_amount == discounted_total == Decimal("88.00")
        # 优惠守恒:严格等于原优惠
        assert parent.model.discount_amount + child.model.discount_amount == Decimal("12.00")
        # 行级优惠也守恒
        all_shares = [l.discount_share for l in parent.lines] + [l.discount_share for l in child.lines]
        assert sum(all_shares) == Decimal("12.00")

        # 选中行(101 的 20 + 103 的 50 = 70)进子单,权重 70/30
        # 12 * 0.7 = 8.40 子单优惠,父单 3.60
        assert child.model.discount_amount == Decimal("8.40")
        assert parent.model.discount_amount == Decimal("3.60")
        assert [l.sku_id for l in child.lines] == [101, 103]
        assert [l.sku_id for l in parent.lines] == [102]

        # 子单是独立单号,CREATED 档,remark 记溯源
        assert child.model.order_sn != parent_sn
        assert child.model.status == "created"
        assert child.model.remark == f"split-from:{parent_sn}"
        assert child.model.total_amount == Decimal("61.60")  # 70 - 8.40
        assert parent.model.total_amount == Decimal("26.40")  # 30 - 3.60

        assert [e["type"] for e in parent.events] == ["order.split"]
        assert parent.events[0]["payload"]["child_order_sn"] == child.model.order_sn

    def test_split_all_lines_rejected(self, db_session):
        svc = make_service(db_session)
        agg = svc.create_order(7, [{"sku_id": 101, "qty": 1}, {"sku_id": 102, "qty": 1}])
        with pytest.raises(ValidationError):
            split_order(db_session, agg.model.order_sn, [0, 1])

    def test_split_index_out_of_range(self, db_session):
        svc = make_service(db_session)
        agg = svc.create_order(7, [{"sku_id": 101, "qty": 1}])
        with pytest.raises(ValidationError):
            split_order(db_session, agg.model.order_sn, [5])

    def test_split_paid_rejected(self, db_session):
        svc = make_service(db_session)
        agg = svc.create_order(7, [{"sku_id": 101, "qty": 1}, {"sku_id": 102, "qty": 1}])
        agg.mark_paid()
        db_session.flush()
        with pytest.raises(OrderStateError):
            split_order(db_session, agg.model.order_sn, [0])

    def test_split_lines_persisted_correctly(self, db_session):
        # 挪行是真挪(order_id 改挂),不是复制
        svc = make_service(db_session)
        agg = svc.create_order(7, [{"sku_id": 101, "qty": 1}, {"sku_id": 102, "qty": 1}])
        parent, child = split_order(db_session, agg.model.order_sn, [1])
        repo = OrderRepository(db_session)
        parent_lines = repo.load_lines(parent.model.id)
        child_lines = repo.load_lines(child.model.id)
        assert [l.sku_id for l in parent_lines] == [101]
        assert [l.sku_id for l in child_lines] == [102]
        # 行数没变多
        assert len(parent_lines) + len(child_lines) == 2

"""结算服务:建单/幂等/状态推进。

注意 test_same_token_blocks_second_create 系列是特征测试
(characterization test):锁定的是 #VT-2217 的现状行为(幂等查重
不带 merchant scope、按 token 后缀模糊匹配),不是期望行为。修复
#VT-2217 时这些断言要跟着改,别当成回归基线保留。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

import vela.domain.settlement  # noqa: F401 - 注册模型建表
from vela.config.errors import ConflictError, ValidationError
from vela.domain.settlement import SettlementService


def _orders(*amounts):
    return [
        {"order_sn": f"O{i}", "amount": Decimal(a), "kind": "SALE"}
        for i, a in enumerate(amounts)
    ]


@pytest.fixture
def service(db_session):
    # 费率给个整数好算的,断言里不出现舍入噪音
    return SettlementService(db_session, fee_rate=Decimal("0.10"))


class TestCreateSettlement:
    def test_amounts_and_lines(self, service):
        model = service.create_settlement(7, _orders("100.00", "50.00"))
        assert model.settlement_sn.startswith("VLS")
        assert model.status == "draft"
        assert model.gross_amount == Decimal("150.00")
        assert model.fee_amount == Decimal("15.00")
        assert model.net_amount == Decimal("135.00")
        assert [line.order_sn for line in model.lines] == ["O0", "O1"]
        assert [line.fee for line in model.lines] == [Decimal("10.00"), Decimal("5.00")]
        # 默认账期天数落库(改表不影响已建单的快照口径)
        assert model.terms_days == 30

    def test_custom_terms_days(self, service):
        model = service.create_settlement(7, _orders("10.00"), terms_days=7)
        assert model.terms_days == 7

    def test_validation(self, service):
        with pytest.raises(ValidationError):
            service.create_settlement(0, _orders("10.00"))
        with pytest.raises(ValidationError):
            service.create_settlement(7, [])


class TestIdempotency:
    def test_same_token_blocks_second_create(self, service):
        # 特征测试(#VT-2217):同 token 二次建单被拦,行为是现状不是期望
        first = service.create_settlement(7, _orders("10.00"), token="tok-1")
        with pytest.raises(ConflictError) as exc:
            service.create_settlement(7, _orders("99.00"), token="tok-1")
        assert exc.value.detail["settlement_sn"] == first.settlement_sn

    def test_cross_merchant_same_token_also_blocked(self, service):
        # 特征测试(#VT-2217):幂等查重不带 merchant 过滤,跨商户同 token
        # 被误拦——这行断言锁定的是 bug 本身,修复后应改为放行/按商户区分
        service.create_settlement(7, _orders("10.00"), token="shared-tok")
        with pytest.raises(ConflictError):
            service.create_settlement(8, _orders("10.00"), token="shared-tok")

    def test_no_token_no_idempotency(self, service):
        # 不带 token 的老调用方不做幂等,随便重推(和 order 域同款行为)
        a = service.create_settlement(7, _orders("10.00"))
        b = service.create_settlement(7, _orders("10.00"))
        assert a.settlement_sn != b.settlement_sn
        assert a.idem_key is None

    def test_idem_key_stores_full_key(self, service):
        model = service.create_settlement(7, _orders("10.00"), token="tok-9")
        # 列里存完整 key,查重却只模糊匹配 token——这个错位就是 #VT-2217
        assert model.idem_key == "settlement_push:tok-9"


class TestStateFlow:
    def test_confirm_push_settle(self, service):
        # service 里时间走 utc_now(),这里只断时间戳存在且单调,不锁具体值
        model = service.create_settlement(7, _orders("100.00"))
        assert model.confirmed_at is None

        service.confirm(model.settlement_sn)
        assert model.status == "confirmed"
        assert model.confirmed_at is not None

        event = service.push(model.settlement_sn)
        assert model.status == "pushed"
        assert model.pushed_at >= model.confirmed_at
        assert event["type"] == "settlement.pushed"
        assert event["payload"]["settlement_sn"] == model.settlement_sn

        service.mark_settled(model.settlement_sn)
        assert model.status == "settled"
        assert model.settled_at >= model.pushed_at

    def test_settle_directly_from_draft_rejected(self, service):
        model = service.create_settlement(7, _orders("10.00"))
        with pytest.raises(ConflictError):
            service.mark_settled(model.settlement_sn)
        assert model.status == "draft"

    def test_double_confirm_rejected(self, service):
        model = service.create_settlement(7, _orders("10.00"))
        service.confirm(model.settlement_sn)
        with pytest.raises(ConflictError):
            service.confirm(model.settlement_sn)

    def test_push_before_confirm_rejected(self, service):
        model = service.create_settlement(7, _orders("10.00"))
        with pytest.raises(ConflictError):
            service.push(model.settlement_sn)

    def test_unknown_sn(self, service):
        from vela.config.errors import NotFoundError

        with pytest.raises(NotFoundError):
            service.confirm("VLS000000")


def test_overdue_via_service(service, frozen_clock):
    # is_overdue 吃 dict,宽表/ORM 两侧共用一套判定
    from vela.domain.settlement import is_overdue

    model = service.create_settlement(7, _orders("10.00"))
    service.confirm(model.settlement_sn)

    now = frozen_clock.now()
    row = {
        "status": model.status,
        "confirmed_at": model.confirmed_at,
        "terms_days": model.terms_days,
    }
    # 刚确认,30 天账期还没到
    assert is_overdue(row, now) is False
    # 时间推过账期,仍未结清 -> 逾期
    frozen_clock.advance(31 * 24 * 3600)
    assert is_overdue(row, frozen_clock.now()) is True

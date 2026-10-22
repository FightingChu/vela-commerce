"""核销链路:幂等 / 限额 / 窗口 / 总量 / 退券。

文件顶部 import 两个模型模块,确保建表(conftest 的 db_session 靠
Base.metadata.create_all,模型没注册就建不出表)。
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import select

import vela.domain.promotion.coupon_model
import vela.domain.promotion.redemption_model  # noqa: F401
from vela.config.clocks import utc_now
from vela.domain.promotion.coupon_model import CouponKind, CouponModel
from vela.domain.promotion.errors import (
    CouponExhaustedError,
    CouponUnavailableError,
    QuotaExceededError,
)
from vela.domain.promotion.redemption_model import CouponRedemptionModel
from vela.domain.promotion.repository import RedemptionRepository
from vela.domain.promotion.service import CouponService

D = Decimal


def _mk_coupon(session, code="SAVE20", **kw) -> CouponModel:
    base = {
        "code": code,
        "title": "测试券",
        "kind": CouponKind.NO_THRESHOLD,
        "threshold_amount": D("0"),
        "discount_amount": D("20"),
        "discount_rate": D("1.000"),
        "stackable": False,
        "total_quota": 10,
        "used_quota": 0,
        "per_customer_limit": 1,
        "valid_from": None,
        "valid_to": None,
        "enabled": True,
    }
    base.update(kw)
    coupon = CouponModel(**base)
    session.add(coupon)
    session.flush()
    return coupon


@pytest.fixture
def svc(db_session):
    return CouponService(db_session)


class TestRedeemHappyPath:
    def test_returns_discount_and_moves_quota(self, db_session, svc):
        coupon = _mk_coupon(db_session)
        got = svc.redeem("SAVE20", "c1", "O1", D("100"))
        assert got == D("20")
        assert coupon.used_quota == 1
        rows = list(RedemptionRepository(db_session).find_by_order("O1"))
        assert len(rows) == 1
        assert rows[0].customer_id == "c1"
        assert rows[0].discount_taken == D("20")
        assert rows[0].redeemed_at is not None

    def test_event_emitted(self, db_session, svc):
        _mk_coupon(db_session)
        svc.redeem("SAVE20", "c1", "O1", D("100"), token="tok-1")
        events = db_session.info["vela_events"]
        assert len(events) == 1
        assert events[0]["type"] == "promotion.coupon_redeemed"
        # MONEY_COLUMN 是 Numeric(18,4),从库回读后是 4 位小数
        assert Decimal(events[0]["payload"]["discount_taken"]) == D("20")

    def test_token_placeholder_falls_back_to_order_sn(self, db_session, svc):
        # 老网关发 "-1",normalize 后为空,幂等键退回 order_sn,不应抛 ValueError
        _mk_coupon(db_session)
        assert svc.redeem("SAVE20", "c1", "O1", D("100"), token="-1") == D("20")


class TestRedeemIdempotent:
    def test_same_order_returns_previous_result(self, db_session, svc):
        coupon = _mk_coupon(db_session)
        first = svc.redeem("SAVE20", "c1", "O1", D("100"))
        second = svc.redeem("SAVE20", "c1", "O1", D("100"))
        assert first == second == D("20")
        assert coupon.used_quota == 1  # 没有重复扣额度
        rows = list(RedemptionRepository(db_session).find_by_order("O1"))
        assert len(rows) == 1

    def test_same_order_other_order_still_counts(self, db_session, svc):
        coupon = _mk_coupon(db_session, per_customer_limit=2)
        svc.redeem("SAVE20", "c1", "O1", D("100"))
        assert svc.redeem("SAVE20", "c1", "O2", D("100")) == D("20")
        assert coupon.used_quota == 2


class TestQuota:
    def test_per_customer_limit(self, db_session, svc):
        _mk_coupon(db_session, per_customer_limit=1)
        svc.redeem("SAVE20", "c1", "O1", D("100"))
        with pytest.raises(QuotaExceededError):
            svc.redeem("SAVE20", "c1", "O2", D("100"))

    def test_total_quota_exhausted(self, db_session, svc):
        _mk_coupon(db_session, total_quota=1)
        svc.redeem("SAVE20", "c1", "O1", D("100"))
        with pytest.raises(CouponExhaustedError):
            svc.redeem("SAVE20", "c2", "O2", D("100"))


class TestWindowAndAvailability:
    def test_not_started(self, db_session, svc):
        now = utc_now()
        _mk_coupon(db_session, valid_from=now + dt.timedelta(hours=1))
        with pytest.raises(CouponUnavailableError):
            svc.redeem("SAVE20", "c1", "O1", D("100"))

    def test_expired(self, db_session, svc):
        now = utc_now()
        _mk_coupon(db_session, valid_to=now - dt.timedelta(minutes=1))
        with pytest.raises(CouponUnavailableError):
            svc.redeem("SAVE20", "c1", "O1", D("100"))

    def test_disabled(self, db_session, svc):
        _mk_coupon(db_session, enabled=False)
        with pytest.raises(CouponUnavailableError):
            svc.redeem("SAVE20", "c1", "O1", D("100"))

    def test_unknown_code(self, db_session, svc):
        with pytest.raises(CouponUnavailableError):
            svc.redeem("NOPE", "c1", "O1", D("100"))

    def test_below_threshold_no_benefit(self, db_session, svc):
        _mk_coupon(db_session, kind=CouponKind.THRESHOLD,
                   threshold_amount=D("100"), discount_amount=D("20"))
        with pytest.raises(CouponUnavailableError):
            svc.redeem("SAVE20", "c1", "O1", D("50"))


class TestRelease:
    def test_release_restores_quota_and_drops_row(self, db_session, svc):
        coupon = _mk_coupon(db_session)
        svc.redeem("SAVE20", "c1", "O1", D("100"))
        released = svc.release("O1")
        assert len(released) == 1
        assert coupon.used_quota == 0
        left = db_session.execute(
            select(CouponRedemptionModel).where(CouponRedemptionModel.order_sn == "O1")
        ).scalars().all()
        assert left == []
        types = [e["type"] for e in db_session.info["vela_events"]]
        assert types == [
            "promotion.coupon_redeemed",
            "promotion.coupon_released",
        ]

    def test_release_idempotent(self, db_session, svc):
        _mk_coupon(db_session)
        svc.redeem("SAVE20", "c1", "O1", D("100"))
        svc.release("O1")
        assert svc.release("O1") == []  # 二次退券安静返回,quota 也不会变负

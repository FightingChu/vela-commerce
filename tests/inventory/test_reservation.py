"""预占纯逻辑层:过期 / 部分释放 / token / TTL 策略。"""

from __future__ import annotations

import datetime as dt

import pytest

from vela.config.constants import RESERVATION_DEFAULT_TTL
from vela.domain.inventory.reservation import (
    BulkReservationPolicy,
    FlashSaleReservationPolicy,
    Reservation,
    ReservationPolicy,
    as_token,
    release_partial,
)


def _rsv(**kw):
    base = {
        "id": 7,
        "sku_id": 101,
        "warehouse": "MAIN",
        "qty": 5,
        "order_sn": "VL-TEST",
        "ttl_seconds": 900,
        "created_at": dt.datetime(2026, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc),
    }
    base.update(kw)
    return Reservation(**base)


class TestIsExpired:
    def test_not_expired_before_ttl(self):
        rsv = _rsv()
        now = rsv.created_at + dt.timedelta(seconds=899)
        assert rsv.is_expired(now) is False

    def test_expired_at_boundary(self):
        # 到点即过期,含等号——job 侧宁可多杀不可漏放
        rsv = _rsv()
        assert rsv.is_expired(rsv.created_at + dt.timedelta(seconds=900)) is True

    def test_remaining_tracks_releases(self):
        rsv = _rsv()
        rsv.released_qty = 2
        assert rsv.remaining == 3


class TestReleasePartial:
    def test_ok_within_remaining(self):
        rsv = _rsv(qty=5)
        release_partial(rsv, 3)
        assert rsv.released_qty == 3
        assert rsv.released_at is None  # 没放完不打时间戳

    def test_over_remaining_raises(self):
        rsv = _rsv(qty=5)
        with pytest.raises(ValueError):
            release_partial(rsv, 6)

    def test_full_release_marks_released_at(self):
        rsv = _rsv(qty=5)
        release_partial(rsv, 5)
        assert rsv.released_at is not None


class TestAsToken:
    def test_format(self):
        assert as_token(_rsv(id=42)) == "rsv-42"


class TestTtlPolicy:
    def test_class_default(self):
        assert ReservationPolicy.default_ttl == RESERVATION_DEFAULT_TTL
        assert ReservationPolicy().default_ttl == 900

    def test_instance_overrides_class(self):
        assert ReservationPolicy(ttl=60).default_ttl == 60

    def test_flash_sale_reads_from_class(self):
        # 不写 __init__,读的就是类属性
        assert FlashSaleReservationPolicy().default_ttl == 300
        assert FlashSaleReservationPolicy(ttl=120).default_ttl == 120

    def test_bulk_policy_via_super(self):
        assert BulkReservationPolicy().default_ttl == 3600
        assert BulkReservationPolicy(ttl=7200).default_ttl == 7200

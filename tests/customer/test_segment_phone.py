"""脱敏/归一边界 + 纯函数圈选(tier/RFM/recency),不碰数据库。"""

from __future__ import annotations

import datetime as dt
import decimal
import types

import pytest

from vela.domain.customer.phone import is_masked, mask_phone, normalize_phone
from vela.domain.customer.segment import rfm_tier, segment_by_recency, segment_by_tier
from vela.domain.customer.tier import Tier, can_downgrade, next_tier, tier_rate

NOW = dt.datetime(2026, 10, 19, tzinfo=dt.timezone.utc)


def _cust(cid, tier):
    return types.SimpleNamespace(id=cid, tier=tier)


class TestMaskPhone:
    def test_basic(self):
        assert mask_phone("13812345678") == "138****5678"

    def test_normalizes_before_masking(self):
        assert mask_phone("+8613812345678") == "138****5678"
        assert mask_phone("138 1234 5678") == "138****5678"

    @pytest.mark.parametrize("bad", ["", "12345", "1381234567", "138123456789", "abcdefghijk"])
    def test_illegal_length_raises(self, bad):
        with pytest.raises(ValueError):
            mask_phone(bad)


class TestNormalizePhone:
    def test_strips_whitespace_and_prefix(self):
        assert normalize_phone("+8613812345678") == "13812345678"
        assert normalize_phone("8613812345678") == "13812345678"
        assert normalize_phone(" 138 1234 5678 ") == "13812345678"

    def test_plain_passthrough(self):
        assert normalize_phone("13812345678") == "13812345678"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            normalize_phone("")


class TestIsMasked:
    def test_masked(self):
        assert is_masked("138****5678") is True

    def test_plaintext(self):
        assert is_masked("13812345678") is False

    def test_empty_and_none(self):
        assert is_masked("") is False
        assert is_masked(None) is False


class TestTierRules:
    def test_rates(self):
        assert tier_rate("V0") == decimal.Decimal("1.00")
        assert tier_rate("V2") == decimal.Decimal("0.95")
        assert tier_rate(Tier.BLACK) == decimal.Decimal("0.88")

    def test_next_tier_chain(self):
        assert next_tier("V0") is Tier.V1
        assert next_tier(Tier.V3) is Tier.BLACK
        assert next_tier(Tier.BLACK) is None

    def test_can_downgrade(self):
        assert can_downgrade("V2") is True
        assert can_downgrade(Tier.BLACK) is False

    def test_illegal_tier_raises(self):
        with pytest.raises(ValueError):
            tier_rate("V9")


class TestSegmentByTier:
    def test_filters_by_tier(self):
        cs = [_cust(1, "V0"), _cust(2, "V1"), _cust(3, "V1"), _cust(4, "BLACK")]
        assert [c.id for c in segment_by_tier(cs, "V1")] == [2, 3]

    def test_accepts_enum(self):
        cs = [_cust(1, "V0"), _cust(4, "BLACK")]
        assert [c.id for c in segment_by_tier(cs, Tier.BLACK)] == [4]

    def test_no_match(self):
        assert segment_by_tier([_cust(1, "V0")], "V3") == []


class TestSegmentByRecency:
    def test_stale_in_fresh_out(self):
        stats = [
            {"customer_id": 1, "last_order_at": NOW - dt.timedelta(days=200)},
            {"customer_id": 2, "last_order_at": NOW - dt.timedelta(days=10)},
            {"customer_id": 3, "last_order_at": NOW - dt.timedelta(days=91)},
        ]
        assert segment_by_recency(stats, days=90, now=NOW) == [1, 3]

    def test_boundary_exactly_n_days_is_fresh(self):
        stats = [{"customer_id": 9, "last_order_at": NOW - dt.timedelta(days=90)}]
        assert segment_by_recency(stats, days=90, now=NOW) == []

    def test_naive_datetime_treated_as_utc(self):
        last = (NOW - dt.timedelta(days=100)).replace(tzinfo=None)
        assert segment_by_recency(
            [{"customer_id": 5, "last_order_at": last}], days=90, now=NOW
        ) == [5]

    def test_never_ordered_counts_as_stale(self):
        assert segment_by_recency(
            [{"customer_id": 7, "last_order_at": None}], days=90, now=NOW
        ) == [7]

    def test_custom_window(self):
        stats = [{"customer_id": 8, "last_order_at": NOW - dt.timedelta(days=15)}]
        assert segment_by_recency(stats, days=7, now=NOW) == [8]
        assert segment_by_recency(stats, days=30, now=NOW) == []


class TestRfmTier:
    def test_high(self):
        assert rfm_tier(5, 20, decimal.Decimal("8000")) == "高"

    def test_mid(self):
        assert rfm_tier(60, 4, decimal.Decimal("2000")) == "中"

    def test_low(self):
        assert rfm_tier(400, 1, decimal.Decimal("10")) == "低"

    def test_accepts_str_amount(self):
        assert rfm_tier(10, 12, "6000") == "高"

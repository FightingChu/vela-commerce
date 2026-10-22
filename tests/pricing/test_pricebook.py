"""价格册仓储:取价优先级、软删过滤、改价日志。"""

import datetime as dt
from decimal import Decimal
from itertools import count

import pytest
from sqlalchemy import select

import vela.domain.pricing.models  # noqa: F401  确保 create_all 前表已注册
from vela.config.clocks import utc_now
from vela.domain.pricing.models import PriceBookEntryModel, PriceChangeLogModel
from vela.domain.pricing.repository import PriceBookRepository

_seq = count(1)

NOW = utc_now()
DAY = dt.timedelta(days=1)


def make_entry(sku_id=None, *, list_price="100", sale_price=None, channel="",
               effective_from=None, effective_to=None) -> PriceBookEntryModel:
    return PriceBookEntryModel(
        sku_id=sku_id or next(_seq),
        list_price=Decimal(list_price),
        sale_price=Decimal(sale_price) if sale_price is not None else None,
        currency="CNY",
        channel=channel,
        effective_from=effective_from or (NOW - DAY),
        effective_to=effective_to,
    )


@pytest.fixture
def repo(db_session):
    return PriceBookRepository(db_session)


class TestCurrentPrice:
    def test_lowest_effective_price_wins(self, db_session, repo):
        # 同 sku 同渠道两条并行生效,报便宜的那条(唯一约束按 effective_from 区分)
        db_session.add_all([
            make_entry(sku_id=101, list_price="100", sale_price="88",
                       effective_from=NOW - 2 * DAY),
            make_entry(sku_id=101, list_price="95"),  # 无促销价,按 list 95
        ])
        db_session.flush()
        entry = repo.current_price(101)
        assert entry.sale_price == Decimal(88)

    def test_sale_price_null_falls_back_to_list(self, db_session, repo):
        db_session.add(make_entry(sku_id=102, list_price="66"))
        db_session.flush()
        entry = repo.current_price(102)
        assert entry.list_price == Decimal(66)
        assert entry.sale_price is None

    def test_effective_window(self, db_session, repo):
        db_session.add_all([
            make_entry(sku_id=103, list_price="50",
                       effective_from=NOW - 2 * DAY, effective_to=NOW - DAY),
            make_entry(sku_id=103, list_price="60",
                       effective_from=NOW, effective_to=NOW + DAY),
            make_entry(sku_id=103, list_price="70", effective_from=NOW - DAY),
        ])
        db_session.flush()
        # NOW 时刻:第二条刚好 from<=at 但 to>at 才算,第三条无限期也生效,取便宜的 60
        entry = repo.current_price(103, at=NOW)
        assert entry.list_price == Decimal(60)
        # 窗口外只剩无限期那条
        later = repo.current_price(103, at=NOW + 10 * DAY)
        assert later.list_price == Decimal(70)

    def test_channel_scoped(self, db_session, repo):
        db_session.add_all([
            make_entry(sku_id=104, list_price="100", channel=""),
            make_entry(sku_id=104, list_price="80", channel="douyin"),
        ])
        db_session.flush()
        assert repo.current_price(104).list_price == Decimal(100)
        assert repo.current_price(104, channel="douyin").list_price == Decimal(80)
        assert repo.current_price(104, channel="taobao") is None

    def test_soft_deleted_filtered(self, db_session, repo):
        entry = make_entry(sku_id=105, list_price="100", sale_price="42")
        db_session.add(entry)
        db_session.flush()
        assert repo.current_price(105).sale_price == Decimal(42)
        repo.delete(entry)  # 软删
        db_session.flush()
        assert repo.current_price(105) is None

    def test_missing_sku_returns_none(self, repo):
        assert repo.current_price(99999) is None


class TestChangePrice:
    def test_updates_price_and_writes_log(self, db_session, repo):
        entry = make_entry(sku_id=201, list_price="100")
        db_session.add(entry)
        db_session.flush()

        repo.change_price(entry, Decimal("79.90"), "ops.li", reason="双11活动")

        db_session.flush()
        assert entry.sale_price == Decimal("79.90")
        log = db_session.execute(select(PriceChangeLogModel)).scalar_one()
        assert log.entry_id == entry.id
        # old_price 记的是改之前的有效价(list,sale 为空)
        assert log.old_price == Decimal(100)
        assert log.new_price == Decimal("79.90")
        assert log.changed_by == "ops.li"
        assert log.reason == "双11活动"

    def test_old_price_uses_sale_when_present(self, db_session, repo):
        entry = make_entry(sku_id=202, list_price="100", sale_price="90")
        db_session.add(entry)
        db_session.flush()

        repo.change_price(entry, Decimal(85), "ops.wang")
        db_session.flush()

        log = db_session.execute(select(PriceChangeLogModel)).scalar_one()
        assert log.old_price == Decimal(90)
        assert log.reason is None  # 没填 reason 就是空

    def test_price_history_includes_deleted(self, db_session, repo):
        e1 = make_entry(sku_id=203, list_price="100", effective_from=NOW - 3 * DAY)
        e2 = make_entry(sku_id=203, list_price="120", effective_from=NOW - DAY)
        db_session.add_all([e1, e2])
        db_session.flush()
        repo.delete(e1)
        db_session.flush()

        history = repo.price_history(203)
        assert [e.id for e in history] == sorted(
            [e1.id, e2.id], key=lambda i: i
        )
        assert len(history) == 2  # 软删的也在

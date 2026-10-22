"""预占/扣减/释放/对账 的库里全链路。"""

from __future__ import annotations

import pytest

# 顶部 import 域包,模型才会注册进 Base.metadata、建表
import vela.domain.inventory  # noqa: F401
from vela.config.errors import ValidationError
from vela.config.flags import flags
from vela.domain.inventory import reconcile
from vela.domain.inventory.errors import InventoryShortageError
from vela.domain.inventory.item_model import SkuModel
from vela.domain.inventory.reservation_model import ReservationStatus
from vela.domain.inventory.reservation_repo import ReservationRepository
from vela.domain.inventory.reservation_service import consume_reservation, reserve
from vela.domain.inventory.stock_model import StockModel
from vela.domain.inventory.stock_repo import StockRepository
from vela.domain.inventory.stock_service import deduct, rollback

WH = "MAIN"


def _seed_sku(session, on_hand=10) -> tuple[SkuModel, StockModel]:
    sku = SkuModel(sku_code="SKU-T1", name="测试商品")
    session.add(sku)
    session.flush()
    stock = StockRepository(session).get_or_create(sku.id, WH)
    stock.on_hand = on_hand
    session.flush()
    return sku, stock


def _get_stock(session, sku_id) -> StockModel:
    return StockRepository(session).get_or_create(sku_id, WH)


class TestReserveAndConsume:
    def test_reserve_then_consume_then_deduct(self, db_session):
        sku, stock = _seed_sku(db_session, on_hand=10)

        rid = reserve(sku.id, 6, order_sn="VL100", session=db_session)
        assert isinstance(rid, int)
        assert _get_stock(db_session, sku.id).available == 4

        consume_reservation(rid, "VL100", session=db_session)
        stock = _get_stock(db_session, sku.id)
        assert stock.reserved == 0
        assert stock.on_hand == 4  # 10 - 6 真扣

        # 只剩 4,扣 5 必须炸
        with pytest.raises(InventoryShortageError) as err:
            deduct(sku.id, 5, "VL100", WH, session=db_session)
        assert err.value.detail["shortage"] == 1

        st, ledger = deduct(sku.id, 4, "VL100", WH, session=db_session)
        assert st.on_hand == 0
        assert ledger.balance_after == 0

    def test_reserve_shortage_raises(self, db_session):
        sku, _ = _seed_sku(db_session, on_hand=3)
        with pytest.raises(InventoryShortageError):
            reserve(sku.id, 5, order_sn="VL101", session=db_session)

    def test_consume_wrong_order_rejected(self, db_session):
        sku, _ = _seed_sku(db_session)
        rid = reserve(sku.id, 1, order_sn="VL102", session=db_session)
        with pytest.raises(ValidationError):
            consume_reservation(rid, "VL999", session=db_session)

    def test_rollback_restores_on_hand(self, db_session):
        sku, _ = _seed_sku(db_session, on_hand=10)
        st, _ = deduct(sku.id, 4, "VL103", WH, session=db_session)
        assert st.on_hand == 6
        st, ledger = rollback(sku.id, 4, "VL103", WH, session=db_session)
        assert st.on_hand == 10
        assert ledger.direction.value == "IN"


class TestRelease:
    def test_full_release(self, db_session):
        sku, _ = _seed_sku(db_session, on_hand=10)
        rid = reserve(sku.id, 3, order_sn="VL110", session=db_session)
        assert _get_stock(db_session, sku.id).available == 7

        rsv = ReservationRepository(db_session).release(rid)
        assert rsv.status == ReservationStatus.RELEASED
        assert _get_stock(db_session, sku.id).available == 10

    def test_partial_release_blocked_without_flag(self, db_session):
        sku, _ = _seed_sku(db_session, on_hand=10)
        rid = reserve(sku.id, 4, order_sn="VL111", session=db_session)

        with pytest.raises(ValidationError):
            ReservationRepository(db_session).release(rid, qty=1)
        # flag 关着,状态不能被动过
        assert _get_stock(db_session, sku.id).available == 6

    def test_partial_release_with_flag_on(self, db_session):
        sku, _ = _seed_sku(db_session, on_hand=10)
        rid = reserve(sku.id, 4, order_sn="VL112", session=db_session)
        flags().enable("inventory_partial_release")

        rsv = ReservationRepository(db_session).release(rid, qty=1)
        assert rsv.status == ReservationStatus.ACTIVE
        assert rsv.released_qty == 1
        assert _get_stock(db_session, sku.id).available == 7

        # 放完自动转 RELEASED
        rsv = ReservationRepository(db_session).release(rid, qty=3)
        assert rsv.status == ReservationStatus.RELEASED
        assert _get_stock(db_session, sku.id).available == 10

    def test_release_over_remaining_rejected(self, db_session):
        sku, _ = _seed_sku(db_session, on_hand=10)
        rid = reserve(sku.id, 2, order_sn="VL113", session=db_session)
        flags().enable("inventory_partial_release")
        with pytest.raises(ValidationError):
            ReservationRepository(db_session).release(rid, qty=3)


class TestReconcile:
    def test_diff_detects_drift(self, db_session):
        sku, _ = _seed_sku(db_session, on_hand=10)
        snap_a = reconcile.take_snapshot(db_session)

        deduct(sku.id, 2, "VL120", WH, session=db_session)
        snap_b = reconcile.take_snapshot(db_session)

        rows = reconcile.diff(snap_a, snap_b)
        assert len(rows) == 1
        assert rows[0]["sku_id"] == sku.id
        assert rows[0]["warehouse"] == WH
        assert rows[0]["expected"] == 10
        assert rows[0]["actual"] == 8
        assert rows[0]["delta"] == -2

    def test_diff_empty_when_equal(self, db_session):
        _sku, _ = _seed_sku(db_session)
        assert reconcile.diff(
            reconcile.take_snapshot(db_session), reconcile.take_snapshot(db_session)
        ) == []

"""注册/重复注册/脱敏/升降级/默认地址 的库里全链路。"""

from __future__ import annotations

import pytest

# 顶部 import 域包,模型才会注册进 Base.metadata、建表
import vela.domain.customer  # noqa: F401
from vela.config.errors import ConflictError, NotFoundError, ValidationError
from vela.domain.customer import (
    AddressModel,
    AddressRepository,
    CustomerRepository,
    register_customer,
    set_default_address,
    update_tier,
)
from vela.domain.customer.service import EVENTS_KEY


def _add_address(session, customer_id, receiver="张三", *, is_default=False):
    addr = AddressModel(
        customer_id=customer_id,
        receiver=receiver,
        phone="139****0001",
        province="浙江省",
        city="杭州市",
        district="西湖区",
        detail="文一西路 100 号",
        is_default=is_default,
    )
    session.add(addr)
    session.flush()
    return addr


class TestRegister:
    def test_register_ok_and_phone_masked(self, db_session):
        c = register_customer("wx-1001", "小王", "+86 1381234 5678", session=db_session)
        assert c.id is not None
        assert c.phone == "138****5678"
        assert c.tier == "V0"
        assert c.registered_at is not None
        events = db_session.info[EVENTS_KEY]
        assert events[-1]["type"] == "customer.registered"
        assert events[-1]["payload"]["external_id"] == "wx-1001"

    def test_register_without_phone(self, db_session):
        c = register_customer("wx-1002", "小李", session=db_session)
        assert c.phone is None

    def test_register_with_initial_tier(self, db_session):
        c = register_customer("wx-1003", "老周", tier="V1", session=db_session)
        assert c.tier == "V1"

    def test_register_already_masked_phone_kept(self, db_session):
        c = register_customer("wx-1007", "戊", "138****5678", session=db_session)
        assert c.phone == "138****5678"

    def test_register_duplicate_external(self, db_session):
        register_customer("wx-1004", "甲", session=db_session)
        with pytest.raises(ConflictError):
            register_customer("wx-1004", "乙", session=db_session)

    def test_register_bad_tier(self, db_session):
        with pytest.raises(ValidationError):
            register_customer("wx-1005", "丙", tier="V9", session=db_session)

    def test_register_bad_phone(self, db_session):
        with pytest.raises(ValueError):
            register_customer("wx-1006", "丁", "12345", session=db_session)


class TestUpdateTier:
    def test_upgrade(self, db_session):
        c = register_customer("wx-2001", "A", session=db_session)
        update_tier(c.id, "V2", session=db_session)
        assert c.tier == "V2"

    def test_upgrade_to_black(self, db_session):
        c = register_customer("wx-2006", "F", session=db_session)
        update_tier(c.id, "BLACK", session=db_session)
        assert c.tier == "BLACK"

    def test_downgrade_rejected(self, db_session):
        c = register_customer("wx-2002", "B", tier="V3", session=db_session)
        with pytest.raises(ValidationError):
            update_tier(c.id, "V1", session=db_session)
        assert c.tier == "V3"  # 状态不能被动过

    def test_black_downgrade_also_rejected(self, db_session):
        c = register_customer("wx-2007", "G", tier="BLACK", session=db_session)
        with pytest.raises(ValidationError):
            update_tier(c.id, "V3", session=db_session)
        assert c.tier == "BLACK"

    def test_same_tier_idempotent(self, db_session):
        c = register_customer("wx-2003", "C", tier="V1", session=db_session)
        update_tier(c.id, "V1", session=db_session)
        assert c.tier == "V1"

    def test_bad_tier_value(self, db_session):
        c = register_customer("wx-2004", "D", session=db_session)
        with pytest.raises(ValidationError):
            update_tier(c.id, "VV", session=db_session)

    def test_tier_changed_event(self, db_session):
        c = register_customer("wx-2005", "E", session=db_session)
        update_tier(c.id, "V1", session=db_session)
        changed = [
            e for e in db_session.info[EVENTS_KEY] if e["type"] == "customer.tier_changed"
        ]
        assert changed
        assert changed[-1]["payload"] == {
            "customer_id": c.id,
            "old_tier": "V0",
            "new_tier": "V1",
        }


class TestAddress:
    def test_set_default_unsets_others(self, db_session):
        c = register_customer("wx-3001", "H", session=db_session)
        a1 = _add_address(db_session, c.id, is_default=True)
        a2 = _add_address(db_session, c.id, receiver="李四")
        got = set_default_address(c.id, a2.id, session=db_session)
        assert got.is_default is True
        assert a1.is_default is False

    def test_get_default_lookup(self, db_session):
        c = register_customer("wx-3002", "I", session=db_session)
        _add_address(db_session, c.id)
        a2 = _add_address(db_session, c.id, receiver="王五")
        set_default_address(c.id, a2.id, session=db_session)
        assert AddressRepository(db_session).get_default(c.id).id == a2.id

    def test_list_addresses(self, db_session):
        c = register_customer("wx-3003", "J", session=db_session)
        _add_address(db_session, c.id)
        _add_address(db_session, c.id, receiver="赵六")
        assert len(AddressRepository(db_session).list_addresses(c.id)) == 2

    def test_other_customers_address_rejected(self, db_session):
        c1 = register_customer("wx-3004", "K", session=db_session)
        c2 = register_customer("wx-3005", "L", session=db_session)
        a = _add_address(db_session, c1.id)
        with pytest.raises(NotFoundError):
            set_default_address(c2.id, a.id, session=db_session)


class TestRepoLookup:
    def test_get_by_external(self, db_session):
        register_customer("wx-4001", "M", session=db_session)
        assert CustomerRepository(db_session).get_by_external("wx-4001") is not None
        assert CustomerRepository(db_session).get_by_external("nobody") is None

    def test_fetch_by_phone_masks_plaintext(self, db_session):
        c = register_customer("wx-4002", "N", "13812345678", session=db_session)
        repo = CustomerRepository(db_session)
        assert repo.fetch_by_phone("13812345678").id == c.id
        assert repo.fetch_by_phone("138****5678").id == c.id
        assert repo.fetch_by_phone("13900000000") is None

    def test_soft_deleted_customer_hidden(self, db_session):
        c = register_customer("wx-4003", "O", session=db_session)
        repo = CustomerRepository(db_session)
        repo.delete(c)
        db_session.flush()
        assert repo.get_by_external("wx-4003") is None

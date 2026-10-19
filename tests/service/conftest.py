"""tests/service 局部 fixture。

契约模块(checkout/order_query/inventory_ops)的会话入口 _scope 默认
绑全局 session_scope,这里换成注入的 db_session——不 commit、不关,
生命周期归 tests/conftest.py 的 db_session 管。
"""

from __future__ import annotations

import contextlib
import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from vela.config.clocks import utc_now


@pytest.fixture
def svc_session(db_session, monkeypatch) -> Session:
    """把三个契约模块的 _scope 都指到测试会话上。"""

    @contextlib.contextmanager
    def _fake_scope():
        yield db_session

    import vela.service.checkout as checkout_mod
    import vela.service.inventory_ops as inventory_ops_mod
    import vela.service.order_query as order_query_mod

    for mod in (checkout_mod, order_query_mod, inventory_ops_mod):
        monkeypatch.setattr(mod, "_scope", _fake_scope)
    return db_session


@pytest.fixture
def seed_price(svc_session):
    """价格册种子。返回工厂,默认挂 app 渠道。"""

    def _seed(sku_id: int, list_price: str = "10.00", *, channel: str = "app",
              sale_price: str | None = None, tenant: str | None = None):
        from vela.domain.pricing.models import PriceBookEntryModel

        entry = PriceBookEntryModel(
            sku_id=sku_id,
            list_price=Decimal(list_price),
            sale_price=Decimal(sale_price) if sale_price is not None else None,
            currency="CNY",
            channel=channel,
            effective_from=utc_now() - dt.timedelta(days=1),
        )
        if tenant:
            entry.tenant_id = tenant
        svc_session.add(entry)
        svc_session.flush()
        return entry

    return _seed


@pytest.fixture
def seed_stock(svc_session):
    """库存行种子。"""

    def _seed(sku_id: int, *, on_hand: int = 100, warehouse: str = "MAIN",
              tenant: str | None = None):
        from vela.domain.inventory.stock_model import StockModel

        stock = StockModel(
            sku_id=sku_id, warehouse=warehouse, on_hand=on_hand, reserved=0
        )
        if tenant:
            stock.tenant_id = tenant
        svc_session.add(stock)
        svc_session.flush()
        return stock

    return _seed

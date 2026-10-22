"""订单 HTTP 层。

测试环境用文件 sqlite(settings 走 VELA_DB_URL),内存库不行——
sqlalchemy 每次连接都是新的空库,请求级 session 根本看不到表。
"""

from __future__ import annotations

import pytest

pytest.importorskip("flask")

from vela.api.app import create_app
from vela.config.constants import TENANT_HEADER, TRACE_HEADER
from vela.db.base import Base
from vela.db.engine import primary_engine, reset_engines
from vela.db.session import reset_session_factories


def _patched_scope():

    from vela.db.session import replica_scope

    # replica_scope 是正经 contextmanager;套 closing 防 generator 半途抛
    return replica_scope()


def _import_all_models():
    # 建全表前得让所有 models 模块先注册进 Base.metadata,和根 conftest 同款套路
    import vela.auditing.models
    import vela.domain.customer.models
    import vela.domain.inventory.item_model
    import vela.domain.inventory.reservation_model
    import vela.domain.inventory.stock_model
    import vela.domain.order.models
    import vela.domain.order.returns
    import vela.domain.pricing.models
    import vela.domain.promotion.coupon_model
    import vela.domain.promotion.redemption_model
    import vela.domain.settlement.models
    import vela.messaging.queue_model
    import vela.tenancy.models  # noqa: F401


@pytest.fixture()
def api_env(monkeypatch, tmp_path):
    db_path = tmp_path / "api.db"
    monkeypatch.setenv("VELA_DB_URL", f"sqlite:///{db_path}")
    import vela.config.settings as settings_mod

    settings_mod.reset_settings()
    reset_engines()
    reset_session_factories()
    _import_all_models()
    Base.metadata.create_all(primary_engine())
    # 基础库 session_scope 没挂 @contextmanager,`with` 会炸(AttributeError);
    # service 契约模块用它当 _scope。db 侧修复前,测试里临时换成
    # replica_scope(正经的 contextmanager,同 URL 同库),修好后删这段。
    import vela.service.order_query as _oq

    monkeypatch.setattr(_oq, "_scope", _patched_scope, raising=False)
    yield
    reset_engines()
    reset_session_factories()
    settings_mod.reset_settings()


@pytest.fixture()
def client(api_env):
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_get_missing_order_returns_404_json(client):
    pytest.importorskip("vela.service.order_query")
    resp = client.get("/api/v1/orders/VL20991231001")
    assert resp.status_code == 404
    body = resp.get_json()
    assert set(body) == {"code", "message"}
    assert body["code"]  # 错误码非空,message 给人看


def test_checkout_uses_service_contract(client, monkeypatch):
    svc = pytest.importorskip("vela.service.checkout")
    seen = {}

    def fake_create_checkout(customer_id, lines, *, channel="app", tenant=None,
                             token=None, trace=None):
        seen["args"] = (customer_id, list(lines), channel, tenant, token, trace)
        return {"order_sn": "VL26010100001", "status": "CREATED"}

    monkeypatch.setattr(svc, "create_checkout", fake_create_checkout)

    resp = client.post(
        "/api/v1/orders/checkout",
        json={
            "customer_id": 9527,
            "lines": [{"sku_id": 1, "qty": 2}],
            "channel": "miniapp",
            "token": "idem-001",
        },
        headers={TENANT_HEADER: "shop-a", TRACE_HEADER: "trace-001"},
    )
    assert resp.status_code == 201
    assert resp.get_json()["order_sn"] == "VL26010100001"
    customer_id, lines, channel, tenant, token, trace = seen["args"]
    # 契约逐项核对,签名改了这里先红
    assert customer_id == 9527
    assert lines == [{"sku_id": 1, "qty": 2}]
    assert channel == "miniapp"
    assert tenant == "shop-a"
    assert token == "idem-001"
    assert trace == "trace-001"


def test_checkout_rejects_empty_lines(client):
    resp = client.post("/api/v1/orders/checkout", json={"customer_id": 1, "lines": []})
    # pydantic 校验失败由 app 级 handler 统一映射成 400 + 错误体
    assert resp.status_code == 400
    body = resp.get_json()
    assert set(body) == {"code", "message"}
    assert "lines" in body["message"]

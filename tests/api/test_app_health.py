# -*- coding: utf-8 -*-
"""app 工厂 + /healthz。不连库也能跑:探活失败标 degraded,不抛。"""

from __future__ import annotations

import pytest

from vela.api.app import create_app
from vela.config.constants import TENANT_HEADER, TRACE_HEADER


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_healthz_shape(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.get_json()
    assert set(body) == {"status", "db", "bus"}
    # 测试环境大概率没有 pg,db 探活失败属正常,不能让请求挂掉
    assert body["status"] in ("ok", "degraded")
    assert isinstance(body["db"], bool)
    assert isinstance(body["bus"], bool)


def test_trace_header_echo(client):
    resp = client.get("/healthz", headers={TRACE_HEADER: "trace-abc-123"})
    assert resp.status_code == 200
    assert resp.headers[TRACE_HEADER] == "trace-abc-123"


def test_trace_header_generated_when_missing(client):
    resp = client.get("/healthz")
    # 没带 trace 头要现生成并回写,网关日志靠这个对齐
    assert resp.headers.get(TRACE_HEADER)


def test_tenant_header_enters_context(client):
    # 租户头合法时请求能走通;超长的会被 tenant_context 拒掉
    resp = client.get("/healthz", headers={TENANT_HEADER: "shop-a"})
    assert resp.status_code == 200

    resp = client.get("/healthz", headers={TENANT_HEADER: "x" * 33})
    assert resp.status_code == 403
    assert set(resp.get_json()) == {"code", "message"}


def test_unknown_route_returns_json_404(client):
    resp = client.get("/api/v1/definitely-not-here")
    assert resp.status_code == 404
    body = resp.get_json()
    assert set(body) == {"code", "message"}

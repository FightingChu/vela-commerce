"""EventBus:订阅 / 通配 / 异常隔离 / 无订阅者。"""

from __future__ import annotations

from vela.domain.shared.events import make_event
from vela.messaging import EventBus, get_bus, publish, subscribe


class TestSubscribePublish:
    def test_exact_match_dispatches(self):
        bus = EventBus()
        got = []
        bus.subscribe("order.paid", got.append)
        n = bus.publish(make_event("order.paid", {"order_id": 1}))
        assert n == 1
        assert got[0]["payload"]["order_id"] == 1

    def test_exact_no_match_other_type(self):
        bus = EventBus()
        got = []
        bus.subscribe("order.paid", got.append)
        bus.publish(make_event("order.shipped"))
        assert got == []

    def test_same_handler_twice_dispatches_once(self):
        bus = EventBus()
        calls = []

        def h(event):
            calls.append(event)

        bus.subscribe("order.paid", h)
        bus.subscribe("order.paid", h)
        assert bus.publish(make_event("order.paid")) == 1
        assert len(calls) == 1


class TestWildcard:
    def test_prefix_wildcard(self):
        bus = EventBus()
        got = []
        bus.subscribe("order.*", got.append)
        assert bus.publish(make_event("order.paid")) == 1
        assert bus.publish(make_event("order.shipped")) == 1
        assert bus.publish(make_event("inventory.low")) == 0
        assert len(got) == 2

    def test_wildcard_does_not_match_sibling_domain(self):
        # "order.*" 不该匹配 "orders.paid" 这种近亲
        bus = EventBus()
        got = []
        bus.subscribe("order.*", got.append)
        bus.publish(make_event("orders.paid"))
        assert got == []


class TestExceptionIsolation:
    def test_bad_handler_does_not_kill_others(self):
        bus = EventBus()
        ok = []

        def boom(event):
            raise RuntimeError("handler 挂了")

        bus.subscribe("order.paid", boom)
        bus.subscribe("order.paid", ok.append)
        # 不向外抛
        n = bus.publish(make_event("order.paid"))
        assert n == 2
        assert len(ok) == 1

    def test_bad_handler_wildcard_batch(self):
        bus = EventBus()

        def boom(event):
            raise ValueError("x")

        seen = []
        bus.subscribe("order.*", boom)
        bus.subscribe("order.*", seen.append)
        bus.publish(make_event("order.cancelled"))
        assert len(seen) == 1


class TestNoSubscriber:
    def test_publish_without_subscribers(self):
        bus = EventBus()
        assert bus.publish(make_event("order.paid")) == 0


class TestModuleLevelBus:
    def test_get_bus_singleton(self):
        assert get_bus() is get_bus()

    def test_module_subscribe_publish(self):
        got = []
        subscribe("test.echo", got.append)
        try:
            assert publish(make_event("test.echo")) >= 1
            assert any(e["type"] == "test.echo" for e in got)
        finally:
            get_bus()._handlers.pop("test.echo", None)

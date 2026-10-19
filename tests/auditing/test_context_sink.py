"""审计上下文与 sink 的基础行为。

只测 context/redact/sink 三块纯逻辑;DbSink 与 service 走的是
同一套模型写入,放在后续 db 相关用例里补(见 #VT-1210)。
"""

from __future__ import annotations

import json

import pytest

from vela.auditing.context import bind, child, current, redact, unbind
from vela.auditing.sink import JsonlSink, MemorySink


@pytest.fixture(autouse=True)
def _clean_ctx():
    unbind()
    yield
    unbind()


class TestContext:
    def test_bind_then_current_then_unbind(self):
        assert current() is None
        ctx = bind("op-alice", trace="tr-1", tenant="acme")
        assert current() is ctx
        assert ctx.actor == "op-alice"
        assert ctx.trace == "tr-1"
        assert ctx.tenant == "acme"
        unbind()
        assert current() is None

    def test_rebind_overrides(self):
        # 重复 bind 覆盖,不叠加
        bind("a")
        bind("b", trace="t2")
        ctx = current()
        assert ctx.actor == "b"
        assert ctx.trace == "t2"

    def test_unbind_without_bind_is_noop(self):
        unbind()  # 不应抛错
        assert current() is None


class TestRedact:
    def test_keeps_head_and_tail_2(self):
        assert redact("13812345678") == "13" + "*" * 7 + "78"

    def test_short_value_fully_masked(self):
        assert redact("1234") == "****"
        assert redact("ab") == "**"

    def test_boundary_len5(self):
        assert redact("12345") == "12*45"


class TestChild:
    def test_child_inherits_trace_tenant(self):
        bind("parent", trace="tr-9", tenant="acme")
        c = child("worker")
        assert c.actor == "worker"
        assert c.trace == "tr-9"
        assert c.tenant == "acme"
        assert c.at is not None

    def test_child_without_context_raises(self):
        from vela.config.errors import ValidationError

        with pytest.raises(ValidationError):
            child("worker")


class TestJsonlSink:
    def test_appends_jsonl_lines(self, tmp_path):
        path = tmp_path / "logs" / "audit.jsonl"
        sink = JsonlSink(path)  # 目录不存在要自动建
        sink.write({"actor": "a", "action": "order.cancel", "n": 1})
        sink.write({"actor": "b", "action": "order.refund", "n": 2})

        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first == {"actor": "a", "action": "order.cancel", "n": 1}
        assert json.loads(lines[1])["n"] == 2

    def test_chinese_not_escaped(self, tmp_path):
        # ensure_ascii=False,合规导出要求人可读
        sink = JsonlSink(tmp_path / "audit.jsonl")
        sink.write({"note": "手工调价"})
        assert "手工调价" in sink.path.read_text(encoding="utf-8")


class TestMemorySink:
    def test_collects_records_in_order(self):
        sink = MemorySink()
        sink.write({"a": 1})
        sink.write({"a": 2})
        assert [r["a"] for r in sink.records] == [1, 2]

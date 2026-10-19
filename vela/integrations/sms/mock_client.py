# -*- coding: utf-8 -*-
"""内存模拟短信客户端。记录所有发送,断言用。"""

from __future__ import annotations

import itertools

from vela.integrations.sms.template import TemplateRegistry, default_registry


class MockSmsClient:
    """实现 SmsClientV2 的鸭子接口(send/status)。"""

    def __init__(self, registry: TemplateRegistry | None = None, fail_count: int = 0):
        self._registry = registry or default_registry()
        self.fail_count = fail_count      # 前 N 次 send 抛 RuntimeError
        self.sent: list[dict] = []        # {phone, template, params, msg_id, text}
        self._seq = itertools.count(1)

    def send(self, phone: str, template_code: str, **params) -> str:
        if self.fail_count > 0:
            self.fail_count -= 1
            raise RuntimeError("模拟短信渠道故障")
        text = self._registry.get(template_code).render(**params)
        msg_id = f"MOCKSMS{next(self._seq):08d}"
        self.sent.append(
            {
                "phone": phone,
                "template": template_code,
                "params": params,
                "msg_id": msg_id,
                "text": text,
            }
        )
        return msg_id

    def status(self, msg_id: str) -> str:
        for item in self.sent:
            if item["msg_id"] == msg_id:
                return "sent"
        return "unknown"

    # 测试辅助
    def sent_to(self, phone: str) -> list[dict]:
        return [s for s in self.sent if s["phone"] == phone]

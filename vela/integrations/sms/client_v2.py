# -*- coding: utf-8 -*-
"""短信网关 v2 客户端。

灰度说明:sms_gateway_v2 关闭时这里直接抛 ConflictError——
不是 bug,是故意的。v1(vela/legacy/sms_v1.py)还在跑老通道,
新客户端如果静默降级到 v1,流量报表会对不上,宁可报错让人来找我们。
灰度全量后(计划 #VT-3105)把这个检查删掉。
"""

from __future__ import annotations

from vela.config.errors import ConflictError, ExternalServiceError
from vela.config.flags import flags
from vela.config.logging import get_logger
from vela.integrations.base import BaseClient
from vela.integrations.sms.mask import mask, mask_in_text
from vela.integrations.sms.template import TemplateRegistry

log = get_logger(__name__)

FLAG_NAME = "sms_gateway_v2"


class SmsClientV2:
    """走公司统一短信网关 v2。发信前模板必须在注册表里。"""

    def __init__(
        self,
        base_url: str,
        transport=None,
        registry: TemplateRegistry | None = None,
        timeout: float = 3.0,
        feature_flags=None,
    ):
        self._client = BaseClient(base_url, transport=transport, timeout=timeout)
        self._registry = registry
        # 注入点给测试用,生产用全局 flags()
        self._flags = feature_flags or flags()

    def send(self, phone: str, template_code: str, **params) -> str:
        """发短信,返回渠道 msg_id。

        日志只打脱敏号,不落明文(合规审计 2024-Q3 抓过一次)。
        """
        if not self._flags.is_on(FLAG_NAME):
            raise ConflictError(
                "sms_gateway_v2 未灰度,请走 v1 通道或联系平台组开 flag",
                detail={"flag": FLAG_NAME},
            )
        registry = self._registry
        if registry is None:
            # 延迟加载内置模板,大多数调用方用默认的就够了
            from vela.integrations.sms.template import default_registry
            registry = default_registry()
        text = registry.get(template_code).render(**params)

        data = self._client.request(
            "POST",
            "/v2/sms/send",
            json_body={"mobile": phone, "template": template_code, "params": params},
        )
        if not isinstance(data, dict) or not data.get("msg_id"):
            raise ExternalServiceError(
                "短信网关响应缺少 msg_id", detail={"body": mask_in_text(str(data))[:256]}
            )
        log.info(
            "sms_sent", to=mask(phone), template=template_code, msg_id=data["msg_id"]
        )
        return data["msg_id"]

    def status(self, msg_id: str) -> str:
        """查发送状态: sent / failed / unknown。"""
        data = self._client.request("GET", f"/v2/sms/status/{msg_id}")
        return (data or {}).get("status", "unknown")

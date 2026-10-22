"""短信适配器。v2 网关客户端受 sms_gateway_v2 flag 控制。"""

from vela.integrations.sms.client_v2 import FLAG_NAME, SmsClientV2
from vela.integrations.sms.mask import is_masked, mask, mask_in_text
from vela.integrations.sms.mock_client import MockSmsClient
from vela.integrations.sms.template import (
    BUILTIN_TEMPLATES,
    SmsTemplate,
    TemplateRegistry,
    default_registry,
)

__all__ = [
    "BUILTIN_TEMPLATES",
    "FLAG_NAME",
    "MockSmsClient",
    "SmsClientV2",
    "SmsTemplate",
    "TemplateRegistry",
    "default_registry",
    "is_masked",
    "mask",
    "mask_in_text",
]

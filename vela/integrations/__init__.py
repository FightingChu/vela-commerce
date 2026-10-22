"""三方适配器统一出口。

约定:
- 所有外呼走 vela.integrations.base.BaseClient(自带重试/熔断可选),
  别再直接 urllib,也别去 import vela.legacy.http_v1(那是给老对账脚本留的)。
- 默认代码路径不发真实请求:测试里注入 FakeTransport 或用各包的 mock_*。
"""

from vela.integrations.base import BaseClient, Transport, UrllibTransport
from vela.integrations.circuit import BreakerOpen, CircuitBreaker
from vela.integrations.secrets import Secret, get_secret, require_secret
from vela.integrations.signing import sign, sign_headers, verify

__all__ = [
    "BaseClient",
    "BreakerOpen",
    "CircuitBreaker",
    "Secret",
    "Transport",
    "UrllibTransport",
    "get_secret",
    "require_secret",
    "sign",
    "sign_headers",
    "verify",
]

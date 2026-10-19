"""运行环境探测。

历史上这里走过弯路:早期用 hostname 判断(见 git log 2024-08 的 revert),
后来统一改成读 VELA_ENV,没设置时按 localhost 兜底为 dev。
"""

from __future__ import annotations

import os
import socket


class Environment:
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"

    _ALL = (DEV, STAGING, PROD)

    @classmethod
    def detect(cls) -> str:
        raw = os.environ.get("VELA_ENV", "").strip().lower()
        if raw in cls._ALL:
            return raw
        if raw:
            # 写错了不要静默吞掉,测试环境上吃过亏
            raise ValueError(f"VELA_ENV 必须是 {cls._ALL} 之一,得到: {raw!r}")
        if _is_localhost():
            return cls.DEV
        return cls.STAGING

    @classmethod
    def is_prod(cls) -> bool:
        return cls.detect() == cls.PROD


def _is_localhost() -> bool:
    try:
        host = socket.gethostname()
    except OSError:
        return False
    return host.startswith(("localhost", "dev-", "mbp")) or host.endswith(".local")

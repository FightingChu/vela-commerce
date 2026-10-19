# -*- coding: utf-8 -*-
"""环境变量密钥存取器。

规矩(安全组 2023-07 定的):
- 密钥只从环境读,不落库、不进配置文件、不写死在代码里。
- 拿到的 Secret 对象 repr 打不出明文,防止 print/debug 把密钥泄进日志。
- 日志里出现密钥名可以,出现密钥值不行。
"""

from __future__ import annotations

import os


class Secret:
    """包一层,避免明文跟着 repr/str 四处跑。"""

    __slots__ = ("_name", "_value")

    def __init__(self, name: str, value: str):
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_value", value)

    def __repr__(self) -> str:
        return f"Secret({self._name}=***)"

    __str__ = __repr__  # f-string 里也不能漏

    # 只暴露裸值,调用处显式 .value,code review 时一眼能盯住
    @property
    def value(self) -> str:
        return object.__getattribute__(self, "_value")

    @property
    def name(self) -> str:
        return object.__getattribute__(self, "_name")


def get_secret(name: str, default: str | None = None) -> Secret | None:
    """读密钥,不存在返回 default(None)。"""
    raw = os.environ.get(name)
    if raw is None:
        return Secret(name, default) if default is not None else None
    return Secret(name, raw)


def require_secret(name: str) -> Secret:
    """读密钥,缺了直接炸——带密钥的服务宁可起不来,别等运行时才发现。"""
    raw = os.environ.get(name)
    if not raw:
        raise LookupError(f"缺少环境变量密钥: {name}")
    return Secret(name, raw)


def redact(text: str, secret: Secret | str | None) -> str:
    """把 text 里出现的密钥值替换成 ***,拼 header/调试串前过一遍。

    只处理单值;批量场景用 auditing.redaction。
    """
    if secret is None:
        return text
    val = secret.value if isinstance(secret, Secret) else secret
    if not val:
        return text
    return text.replace(val, "***")

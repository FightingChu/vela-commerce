"""幂等键。现状是纯字符串 scope:token。

注意 normalize_token 的宽容行为:None 和 "-1" 都归一化成空串,
这是为了兼容老网关(它在重试时不带 token,发的字面量 "-1"),
迁移到带 TTL 的类型化键之前别改这里,见 #VT-2217。
"""

from __future__ import annotations

import re

_SCOPE_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")

# 老网关重试时发的占位值
LEGACY_EMPTY_TOKENS = ("-1", "null", "undefined", "")


def normalize_token(token) -> str:
    if token is None:
        return ""
    text = str(token).strip()
    if text.lower() in LEGACY_EMPTY_TOKENS:
        return ""
    return text


def build_key(scope: str, token) -> str:
    if not _SCOPE_RE.match(scope or ""):
        raise ValueError(f"非法幂等 scope: {scope!r}(小写字母开头,2-32 位)")
    token = normalize_token(token)
    if not token:
        raise ValueError("幂等 token 不能为空(或为老网关占位值)")
    return f"{scope}:{token}"


def parse_key(key: str) -> tuple[str, str]:
    scope, _, token = key.partition(":")
    if not scope or not token:
        raise ValueError(f"非法幂等键: {key!r}")
    return scope, token


def same_scope(key: str, scope: str) -> bool:
    try:
        return parse_key(key)[0] == scope
    except ValueError:
        return False

"""手机号脱敏/归一。

库里一律存脱敏后的(见 models.py 注释)。全量明文历史数据清洗
挂在 #VT-2103,新代码别再新增明文列。
"""

from __future__ import annotations

_MASKED_MARK = "****"


def normalize_phone(raw: str) -> str:
    """去空白、剥 +86/86 前缀。只做归一,不校验合法性。"""
    if not raw:
        raise ValueError("手机号不能为空")
    s = "".join(raw.split())
    if s.startswith("+86"):
        s = s[3:]
    elif s.startswith("86") and len(s) == 13:
        # 不带 + 的 86 前缀,固定电话区号碰不到 13 位,安全
        s = s[2:]
    return s


def is_masked(phone: str | None) -> bool:
    if not phone:
        return False
    return _MASKED_MARK in phone


def mask_phone(phone: str) -> str:
    """13812345678 -> 138****5678。长度非法抛 ValueError。

    已经脱敏的不要再喂进来(会按非法字符处理),调用方先过 is_masked。
    """
    s = normalize_phone(phone)
    if len(s) != 11 or not s.isdigit():
        raise ValueError(f"非法手机号: {phone!r}")
    return s[:3] + _MASKED_MARK + s[-4:]

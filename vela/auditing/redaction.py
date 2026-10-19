"""脱敏规则。合规口径是"日志里不许出现明文个人信息"(见 #VT-1204),
新敏感字段加进 redact_detail 的默认 keys,别在调用点各自散写。"""

from __future__ import annotations

from typing import Any


def mask_phone(value: str) -> str:
    """手机号留前 3 后 4,不足 7 位视为非法输入直接全打码。"""
    if len(value) < 7:
        return "*" * len(value)
    return value[:3] + "****" + value[-4:]


def mask_id_card(value: str) -> str:
    """身份证留前 4 后 4(前 4 含地区码,排查时要用来对片区)。"""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def mask_amount(value: str) -> str:
    # 金额档位也算敏感信息,不看规则统一全遮
    return "****"


_MASKERS = {
    "phone": mask_phone,
    "id_card": mask_id_card,
    "bank_no": lambda v: "*" * len(v),  # 银行卡号连尾号都不留,风控要求
    "amount": mask_amount,
}


def redact_detail(
    detail: dict, keys: tuple = ("phone", "id_card", "bank_no")
) -> dict:
    """返回脱敏副本,原 dict 不动(detail 常常还要继续用在业务侧)。"""
    out: dict[str, Any] = dict(detail)
    for key in keys:
        if key in out and out[key] is not None:
            masker = _MASKERS.get(key)
            out[key] = masker(str(out[key])) if masker else "*" * len(str(out[key]))
    return out

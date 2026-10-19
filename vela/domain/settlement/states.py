"""结算状态机。

FAILED 不是"结算失败"的终态语义:push 之后渠道侧清分失败也落这里,
人工修数后重开新单(没有 FAILED -> DRAFT 的回退边,别加,2025-08
对账事故复盘定的,见 #VT-2077)。
"""

from __future__ import annotations

import enum

from vela.config.errors import ConflictError
from vela.domain.shared import StateMachine


class SettlementStatus(str, enum.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    #: 已推送给渠道/清分侧,pushed_at 记录推送时刻
    PUSHED = "pushed"
    SETTLED = "settled"
    FAILED = "failed"


def _state_name(value) -> str:
    """枚举或裸字符串都收,统一成 name 形式(大写)。"""
    if isinstance(value, SettlementStatus):
        return value.name
    return str(value).upper()


class SettlementStateMachine(StateMachine):
    """值是合法动作名,审计侧靠它区分谁推的。"""

    transitions: dict[str, dict[str, str]] = {
        "DRAFT": {
            "CONFIRMED": "confirm",
            "FAILED": "fail",
        },
        "CONFIRMED": {
            "PUSHED": "push",
            "FAILED": "fail",
        },
        "PUSHED": {
            "SETTLED": "settle",
            "FAILED": "fail",
        },
        "SETTLED": {},
        "FAILED": {},
    }

    @classmethod
    def can_transition(cls, current, target) -> bool:
        return super().can_transition(_state_name(current), _state_name(target))

    @classmethod
    def assert_transition(cls, current, target) -> None:
        cur, tgt = _state_name(current), _state_name(target)
        if not super().can_transition(cur, tgt):
            allowed = sorted(cls.transitions.get(cur, {}))
            raise ConflictError(
                f"结算单状态 {cur} 不允许流转到 {tgt}",
                detail={"current": cur, "target": tgt, "allowed": allowed},
            )

    @classmethod
    def action_for(cls, current, target) -> str | None:
        return super().action_for(_state_name(current), _state_name(target))

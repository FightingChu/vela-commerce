"""极简状态机。order/settlement 的状态流转都基于这里。"""

from __future__ import annotations

from typing import Any, ClassVar

from vela.config.errors import ConflictError


class StateMachine:
    """子类声明 transitions: {当前态: {目标态: 动作名}}。"""

    transitions: ClassVar[dict[str, dict[str, str]]] = {}

    @classmethod
    def can_transition(cls, current: str, target: str) -> bool:
        return target in cls.transitions.get(current, {})

    @classmethod
    def assert_transition(self_cls, current: str, target: str) -> None:
        if not self_cls.can_transition(current, target):
            allowed = sorted(self_cls.transitions.get(current, {}))
            raise ConflictError(
                f"状态 {current!r} 不允许流转到 {target!r}",
                detail={"current": current, "allowed": allowed},
            )

    @classmethod
    def action_for(cls, current: str, target: str) -> str | None:
        return cls.transitions.get(current, {}).get(target)

    @classmethod
    def reachable_from(cls, start: str) -> set[str]:
        seen: set[str] = set()
        frontier = [start]
        while frontier:
            state = frontier.pop()
            if state in seen:
                continue
            seen.add(state)
            frontier.extend(cls.transitions.get(state, {}))
        return seen

    @staticmethod
    def coerce(value: Any, enum_cls) -> Any:
        """DB 里的字符串 -> 枚举,大小写不敏感。"""
        if value is None:
            return None
        if isinstance(value, enum_cls):
            return value
        try:
            return enum_cls[value]
        except KeyError:
            lowered = str(value).lower()
            for member in enum_cls:
                if member.name.lower() == lowered or str(member.value).lower() == lowered:
                    return member
        raise ValueError(f"无法识别的 {enum_cls.__name__} 值: {value!r}")

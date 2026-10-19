"""状态机全分支。测试文件顶部 import 域包,确保模型注册建表。"""

from __future__ import annotations

import pytest

import vela.domain.order  # noqa: F401 - 注册模型建表
from vela.domain.order import OrderStateError, OrderStateMachine, OrderStatus
from vela.domain.order.states import TERMINAL_STATUSES
from vela.domain.shared import StateMachine


def _flatten(transitions):
    for current, targets in transitions.items():
        for target, action in targets.items():
            yield current, target, action


@pytest.mark.parametrize("current,target,action", list(_flatten(OrderStateMachine.transitions)))
def test_legal_transitions(current, target, action):
    assert OrderStateMachine.can_transition(current, target)
    assert OrderStateMachine.action_for(current, target) == action
    OrderStateMachine.assert_transition(current, target)  # 不抛


def test_pay_is_the_only_path_out_of_created_for_money():
    assert OrderStateMachine.action_for("CREATED", "PAID") == "pay"


def test_paid_cannot_cancel():
    # 已支付走退款,这是 2024-03 定的约定
    assert not OrderStateMachine.can_transition("PAID", "CANCELLED")
    with pytest.raises(OrderStateError) as exc:
        OrderStateMachine.assert_transition("PAID", "CANCELLED")
    assert exc.value.detail["current"] == "PAID"
    assert "CANCELLED" not in exc.value.detail["allowed"]


@pytest.mark.parametrize(
    "current,target",
    [
        ("CREATED", "COMPLETED"),
        ("CREATED", "REFUNDED"),
        ("CREATED", "SHIPPED"),  # 未支付不能发货
        ("PARTIAL_SHIPPED", "PAID"),
        ("SHIPPED", "PAID"),
        ("REFUNDED", "PAID"),
        ("REFUNDING", "SHIPPED"),
        ("CANCELLED", "PAID"),
        ("CLOSED", "CREATED"),
    ],
)
def test_illegal_transitions_raise(current, target):
    assert not OrderStateMachine.can_transition(current, target)
    with pytest.raises(OrderStateError):
        OrderStateMachine.assert_transition(current, target)


@pytest.mark.parametrize("state", TERMINAL_STATUSES)
def test_terminal_states_have_no_outgoing(state):
    assert OrderStateMachine.transitions[state] == {}
    assert OrderStateMachine.reachable_from(state) == {state}
    with pytest.raises(OrderStateError):
        OrderStateMachine.assert_transition(state, "PAID")


def test_reachable_from_created():
    reachable = OrderStateMachine.reachable_from("CREATED")
    assert {
        "CREATED",
        "PAID",
        "PARTIAL_SHIPPED",
        "SHIPPED",
        "COMPLETED",
        "REFUNDING",
        "REFUNDED",
        "CANCELLED",
        "CLOSED",
    } <= reachable


def test_reachable_from_paid_excludes_cancel():
    reachable = OrderStateMachine.reachable_from("PAID")
    assert "CANCELLED" not in reachable
    assert "CLOSED" not in reachable


def test_can_transition_accepts_enum():
    assert OrderStateMachine.can_transition(OrderStatus.CREATED, OrderStatus.PAID)
    assert not OrderStateMachine.can_transition(OrderStatus.PAID, OrderStatus.CANCELLED)


def test_coerce_roundtrip():
    assert StateMachine.coerce("created", OrderStatus) is OrderStatus.CREATED
    assert StateMachine.coerce("PAID", OrderStatus) is OrderStatus.PAID
    assert StateMachine.coerce(OrderStatus.REFUNDING, OrderStatus) is OrderStatus.REFUNDING
    with pytest.raises(ValueError):
        StateMachine.coerce("no_such_state", OrderStatus)

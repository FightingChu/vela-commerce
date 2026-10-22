"""下单编排。api 并行任务的契约模块:create_checkout 签名一字不动。

组装逻辑:pricer 走 pricing 域批量询价(缺价由 OrderService 报
ValidationError,缺价禁止裸价下单),reserver 直连 inventory 域的
reserve,凭证(ReservationModel 主键)落进行快照,取消/释放时原样
还回去。

会话入口 _scope 默认走全局 session_scope(job/脚本场景);http 层和
测试通过替换这个模块属性注入会话(见 tests/service/conftest.py),
不要在业务代码里动它。
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from decimal import Decimal

from sqlalchemy.orm import Session

from vela.db import session_scope, tenant_context
from vela.domain.inventory import reserve as inventory_reserve
from vela.domain.order import DuplicateOrderError, OrderService  # noqa: F401 DuplicateOrderError 给调用方 re-export
from vela.domain.pricing import get_quote
from vela.service import trace as trace_mod
from vela.service.converters import line_to_view, money

_scope = session_scope


@contextlib.contextmanager
def _checkout_session(tenant: str | None) -> Iterator[Session]:
    """租户给了就先切上下文再开会话,顺序反了首条 SQL 就串租户。"""
    ctx = tenant_context(tenant) if tenant else contextlib.nullcontext()
    with ctx, _scope() as session:
        yield session


def _build_reserver(session: Session):
    """适配 OrderService 的 reserver 契约: (sku_id, qty, order_sn) -> int。"""

    def reserver(sku_id: int, qty: int, order_sn: str) -> int:
        return inventory_reserve(sku_id, qty, order_sn=order_sn, session=session)

    return reserver


def _build_pricer(session: Session, channel: str):
    """get_quote 返回 {sku: Price|None},OrderService 只认 Decimal 且
    缺价要它自己报错,这里把 None 滤掉交给上层拦。"""

    def pricer(sku_ids) -> dict[int, Decimal]:
        quote = get_quote(list(sku_ids), channel, session=session)
        return {
            sku_id: price.amount
            for sku_id, price in quote.items()
            if price is not None
        }

    return pricer


def create_checkout(
    customer_id: int,
    lines: list[dict],
    *,
    channel: str = "app",
    tenant: str | None = None,
    token: str | None = None,
    trace: str | None = None,
) -> dict:
    """下单主链路:询价 -> 预占 -> 建单,一个事务。

    返回 {"order_sn","total","discount","lines","reservations"}。
    幂等 token 命中抛 DuplicateOrderError(域里翻的,这里不包一层)。
    """
    trace = trace_mod.ensure_trace(trace)

    with _checkout_session(tenant) as session:
        service = OrderService(
            session,
            reserver=_build_reserver(session),
            pricer=_build_pricer(session, channel),
        )
        agg = service.create_order(
            customer_id,
            lines,
            channel=channel,
            token=token,
            trace=trace,
        )
        if tenant:
            # tenant_id 列的 ORM default 恒为 main,隐式上下文不会盖它;
            # 显式租户下单必须手动落,否则查询侧按租户过滤就找不到了
            agg.model.tenant_id = tenant
        session.flush()
        return _to_result(agg)


def _to_result(agg) -> dict:
    lines = [line_to_view(line) for line in agg.lines]
    reservations = [
        view["reservation_ref"] for view in lines if view["reservation_ref"] is not None
    ]
    return {
        "order_sn": agg.model.order_sn,
        "total": money(agg.model.total_amount),
        "discount": money(agg.model.discount_amount),
        "lines": lines,
        "reservations": reservations,
    }

"""报价服务。批量取价入口,给 order/promotion 域调。

历史上这里有个 session 参数没有,靠中间件塞 current_session,
后来 job 侧也要用就加回来了(session=None 时回落 current_session)。
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from vela.db.session import current_session
from vela.domain.pricing.currency import CurrencyEnum
from vela.domain.pricing.price import Price
from vela.domain.pricing.repository import PriceBookRepository


def fetch_pricebook_entries(session, sku_ids, channel, at=None):
    """逐 sku 取生效条目,查不到就跳过(missing 由 get_quote 统一标记)。"""
    repo = PriceBookRepository(session)
    found = {}
    for sku_id in sku_ids:
        entry = repo.current_price(sku_id, channel=channel, at=at)
        if entry is not None:
            found[sku_id] = entry
    return found


def get_effective(entry) -> Price:
    """条目 -> Price,有促销价用促销价。"""
    amount = entry.sale_price if entry.sale_price is not None else entry.list_price
    return Price(amount, CurrencyEnum(entry.currency))


def get_quote(
    sku_ids,
    channel: str = "",
    *,
    session: Session | None = None,
) -> dict:
    """批量报价。返回 {sku_id: Price};缺价的 sku 值为 None,不抛错——
    购物车场景缺一个 sku 不能整单失败,由调用方决定怎么提示。"""
    session = session or current_session()
    entries = fetch_pricebook_entries(session, sku_ids, channel)
    quote: dict[int, Price | None] = {}
    for sku_id in sku_ids:
        entry = entries.get(sku_id)
        quote[sku_id] = get_effective(entry) if entry is not None else None
    return quote

"""客户域事件常量与 make 帮助函数。"""

from __future__ import annotations

import datetime as dt

from vela.domain.shared import make_event

EVENT_CUSTOMER_REGISTERED = "customer.registered"
EVENT_TIER_CHANGED = "customer.tier_changed"


def make_registered_event(
    external_id: str,
    customer_id: int,
    tier: str,
    *,
    trace: str | None = None,
    occurred_at: dt.datetime | None = None,
) -> dict:
    return make_event(
        EVENT_CUSTOMER_REGISTERED,
        {"external_id": external_id, "customer_id": customer_id, "tier": tier},
        trace=trace,
        occurred_at=occurred_at,
    )


def make_tier_changed_event(
    customer_id: int,
    old_tier: str,
    new_tier: str,
    *,
    trace: str | None = None,
    occurred_at: dt.datetime | None = None,
) -> dict:
    return make_event(
        EVENT_TIER_CHANGED,
        {"customer_id": customer_id, "old_tier": old_tier, "new_tier": new_tier},
        trace=trace,
        occurred_at=occurred_at,
    )

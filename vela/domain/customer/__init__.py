"""客户域。import 本包即注册 customers/addresses 表到 Base.metadata。"""

from __future__ import annotations

from vela.domain.customer.events import EVENT_CUSTOMER_REGISTERED, EVENT_TIER_CHANGED
from vela.domain.customer.models import AddressModel, CustomerModel
from vela.domain.customer.phone import is_masked, mask_phone, normalize_phone
from vela.domain.customer.repository import AddressRepository, CustomerRepository
from vela.domain.customer.service import register_customer, set_default_address, update_tier
from vela.domain.customer.tier import Tier, can_downgrade, next_tier, tier_rate
from vela.domain.customer import segment

__all__ = [
    "CustomerModel",
    "AddressModel",
    "Tier",
    "tier_rate",
    "next_tier",
    "can_downgrade",
    "mask_phone",
    "normalize_phone",
    "is_masked",
    "CustomerRepository",
    "AddressRepository",
    "register_customer",
    "update_tier",
    "set_default_address",
    "segment",
    "EVENT_CUSTOMER_REGISTERED",
    "EVENT_TIER_CHANGED",
]

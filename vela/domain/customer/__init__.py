"""客户域。import 本包即注册 customers/addresses 表到 Base.metadata。"""

from __future__ import annotations

from vela.domain.customer import segment
from vela.domain.customer.events import EVENT_CUSTOMER_REGISTERED, EVENT_TIER_CHANGED
from vela.domain.customer.models import AddressModel, CustomerModel
from vela.domain.customer.phone import is_masked, mask_phone, normalize_phone
from vela.domain.customer.repository import AddressRepository, CustomerRepository
from vela.domain.customer.service import register_customer, set_default_address, update_tier
from vela.domain.customer.tier import Tier, can_downgrade, next_tier, tier_rate

__all__ = [
    "EVENT_CUSTOMER_REGISTERED",
    "EVENT_TIER_CHANGED",
    "AddressModel",
    "AddressRepository",
    "CustomerModel",
    "CustomerRepository",
    "Tier",
    "can_downgrade",
    "is_masked",
    "mask_phone",
    "next_tier",
    "normalize_phone",
    "register_customer",
    "segment",
    "set_default_address",
    "tier_rate",
    "update_tier",
]

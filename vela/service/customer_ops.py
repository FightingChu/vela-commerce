"""客户操作编排。注册/查询/等级,给 api 和 legacy 同步 job 共用。

手机号脱敏在 domain.register_customer 里做过了,这层不重复处理;
视图里出的 phone 本来就是脱敏串,可以直接对外。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from vela.config.errors import NotFoundError, ValidationError
from vela.config.logging import get_logger
from vela.domain.customer import (
    AddressRepository,
    CustomerRepository,
    register_customer,
    set_default_address,
    update_tier,
)
from vela.service import audit_bridge

log = get_logger(__name__)


def register(
    session: Session,
    external_id: str,
    nickname: str,
    phone: str | None = None,
    *,
    tier: str = "V0",
    channel: str | None = None,
) -> "object":
    """注册新客。channel 目前只进审计(客户表没有来源列,加列在
    #VT-2168,先记着别丢信息)。重复注册抛 ConflictError。"""
    customer = register_customer(external_id, nickname, phone, tier, session=session)
    audit_bridge.record_admin_action(
        session,
        action="customer.registered",
        target_type="customer",
        target_id=customer.id,
        detail={"external_id": external_id, "channel": channel},
    )
    return customer


def customer_view(session: Session, customer_id: int) -> dict | None:
    """客户档案视图。查无(含软删)返回 None。"""
    try:
        customer = CustomerRepository(session).get(customer_id)
    except NotFoundError:
        return None
    return {
        "customer_id": customer.id,
        "external_id": customer.external_id,
        "nickname": customer.nickname,
        "phone": customer.phone,
        "tier": customer.tier,
        "registered_at": customer.registered_at.isoformat()
        if customer.registered_at
        else None,
        "tags": list(customer.tags or []),
    }


def change_tier(session: Session, customer_id: int, tier: str) -> "object":
    """升降级。降级在 domain 层被拦(只升不降,人工降级走 CRM 工单)。"""
    customer = update_tier(customer_id, tier, session=session)
    audit_bridge.record_admin_action(
        session,
        action="customer.tier_changed",
        target_type="customer",
        target_id=customer_id,
        detail={"to": tier},
    )
    return customer


def default_address(session: Session, customer_id: int) -> dict | None:
    """默认收货地址,下单页预填用。没设过返回 None。"""
    addr = AddressRepository(session).get_default(customer_id)
    if addr is None:
        return None
    return {
        "address_id": addr.id,
        "receiver": addr.receiver,
        "phone": addr.phone,
        "province": addr.province,
        "city": addr.city,
        "district": addr.district,
        "detail": addr.detail,
    }


def make_default_address(session: Session, customer_id: int, address_id: int) -> dict:
    """设默认地址,同客户其余地址自动取消默认。"""
    if not customer_id or not address_id:
        raise ValidationError("customer_id 与 address_id 不能为空")
    addr = set_default_address(customer_id, address_id, session=session)
    log.info("default_address_set", customer_id=customer_id, address_id=address_id)
    return {"address_id": addr.id, "is_default": addr.is_default}

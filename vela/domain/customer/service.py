"""客户注册 / 等级变更 / 默认地址。

等级"只升不降"是运营 2024 定的规矩:自动降级掉折扣引发过客诉
(#VT-1622),人工降级走 CRM 工单。事件挂 session.info,由中间件
统一收走出 outbox,做法同 inventory.stock_service。
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vela.config.errors import ConflictError, NotFoundError, ValidationError
from vela.db import current_session, translate_integrity_error
from vela.domain.customer.events import make_registered_event, make_tier_changed_event
from vela.domain.customer.models import AddressModel, CustomerModel
from vela.domain.customer.phone import is_masked, mask_phone
from vela.domain.customer.repository import AddressRepository, CustomerRepository
from vela.domain.customer.tier import Tier, can_downgrade, rank_of

EVENTS_KEY = "vela_events"


def _emit(session: Session, event: dict) -> None:
    session.info.setdefault(EVENTS_KEY, []).append(event)


def register_customer(
    external_id: str,
    nickname: str,
    phone: str | None = None,
    tier: str = "V0",
    *,
    session: Session | None = None,
) -> CustomerModel:
    """新客注册。手机号脱敏后入库;external_id 全局唯一,重复抛 409。"""
    if not external_id or not nickname:
        raise ValidationError("external_id 与 nickname 不能为空")
    session = session or current_session()
    repo = CustomerRepository(session)
    if repo.get_by_external(external_id) is not None:
        raise ConflictError(
            f"客户已注册: {external_id}", detail={"external_id": external_id}
        )
    try:
        tier_val = Tier(tier)
    except ValueError:
        raise ValidationError(f"非法等级: {tier!r}") from None
    stored_phone = None
    if phone:
        # 渠道侧传来的可能已脱敏,别二次处理
        stored_phone = phone if is_masked(phone) else mask_phone(phone)
    customer = CustomerModel(
        external_id=external_id,
        nickname=nickname,
        phone=stored_phone,
        tier=tier_val.value,
    )
    repo.add(customer)
    try:
        session.flush()
    except IntegrityError as exc:
        # 并发窗口内的重复注册,兜底翻译成 409
        raise translate_integrity_error(exc) from None
    _emit(
        session,
        make_registered_event(external_id, customer.id, tier_val.value, trace=external_id),
    )
    return customer


def update_tier(
    customer_id: int,
    tier: str,
    *,
    session: Session | None = None,
) -> CustomerModel:
    """升降级入口。同档幂等;降级一律拦下。"""
    try:
        new = Tier(tier)
    except ValueError:
        raise ValidationError(f"非法等级: {tier!r}") from None
    session = session or current_session()
    customer = CustomerRepository(session).get(customer_id)
    old = Tier(customer.tier)
    if new is old:
        return customer  # 重复通知(渠道侧会重推),幂等返回
    if rank_of(new) < rank_of(old):
        # 真正的降级要走 can_downgrade 对应的 CRM 审核工单(#VT-1976),
        # 审核流没打通前先简化为直接拒绝,打通后再在这里放行。
        if not can_downgrade(old):
            raise ValidationError(
                f"{old.value} 不允许降级",
                detail={"customer_id": customer_id, "from": old.value, "to": new.value},
            )
        raise ValidationError(
            f"等级不允许从 {old.value} 降到 {new.value},降级需走人工审核",
            detail={"customer_id": customer_id, "from": old.value, "to": new.value},
        )
    customer.tier = new.value
    session.flush()
    _emit(
        session,
        make_tier_changed_event(customer_id, old.value, new.value, trace=str(customer.external_id)),
    )
    return customer


def set_default_address(
    customer_id: int,
    address_id: int,
    *,
    session: Session | None = None,
) -> AddressModel:
    """设默认地址,同客户其余地址自动取消默认。"""
    session = session or current_session()
    repo = AddressRepository(session)
    addr = repo.get(address_id)
    if addr.customer_id != customer_id:
        raise NotFoundError(
            f"地址 {address_id} 不属于客户 {customer_id}",
            detail={"customer_id": customer_id, "address_id": address_id},
        )
    for other in repo.list_addresses(customer_id):
        other.is_default = other.id == address_id
    session.flush()
    return addr

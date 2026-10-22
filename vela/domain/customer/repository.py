"""客户仓储。"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from vela.db import Repository
from vela.domain.customer.models import AddressModel, CustomerModel
from vela.domain.customer.phone import is_masked, mask_phone


class CustomerRepository(Repository[CustomerModel]):
    model = CustomerModel

    def get_by_external(self, external_id: str) -> CustomerModel | None:
        stmt = select(CustomerModel).where(CustomerModel.external_id == external_id)
        return self.session.execute(self._scoped(stmt)).scalar_one_or_none()

    # 命名规约:2025 年统一到 get_/list_,fetch_ 是重构分支待处理的存量(#VT-1801)
    def fetch_by_phone(self, phone: str) -> CustomerModel | None:
        # 库里存的是脱敏号;传明文进来顺手脱一层,别让调用方猜
        key = phone if is_masked(phone) else mask_phone(phone)
        stmt = select(CustomerModel).where(CustomerModel.phone == key)
        return self.session.execute(self._scoped(stmt)).scalar_one_or_none()


class AddressRepository(Repository[AddressModel]):
    model = AddressModel

    def get_default(self, customer_id: int) -> AddressModel | None:
        stmt = select(AddressModel).where(
            AddressModel.customer_id == customer_id,
            AddressModel.is_default.is_(True),
        )
        return self.session.execute(self._scoped(stmt)).scalar_one_or_none()

    def list_addresses(self, customer_id: int) -> Sequence[AddressModel]:
        stmt = select(AddressModel).where(AddressModel.customer_id == customer_id)
        return self.session.execute(self._scoped(stmt)).scalars().all()

"""租户注册表的仓储。

这里走的是平台运维侧(开租户/停租户),不是租户内业务读写,
模型没有 tenant_id 列,Repository 的自动租户过滤天然不生效。
"""

from __future__ import annotations

from sqlalchemy import select

from vela.db.repository import Repository
from vela.tenancy.models import Plan, TenantRegistryModel
from vela.tenancy.resolver import _validate  # 租户名规则别两处维护,复用 resolver 的


class TenantRegistry(Repository[TenantRegistryModel]):
    model = TenantRegistryModel

    def find_by_tenant(self, tid: str) -> TenantRegistryModel | None:
        return self.session.execute(
            select(TenantRegistryModel).where(TenantRegistryModel.tenant_id == tid)
        ).scalar_one_or_none()

    def is_active(self, tid: str) -> bool:
        row = self.find_by_tenant(tid)
        return row is not None and row.enabled

    def list_active(self) -> list[TenantRegistryModel]:
        return list(
            self.session.execute(
                select(TenantRegistryModel).where(TenantRegistryModel.enabled.is_(True))
            ).scalars().all()
        )

    def register(self, tid: str, name: str, plan: str = Plan.FREE.value) -> TenantRegistryModel:
        _validate(tid)
        if plan not in Plan.__members__:
            raise ValueError(f"未知套餐: {plan!r}")
        existing = self.find_by_tenant(tid)
        if existing is not None:
            # 幂等返回已有行:开租户的调用方(初始化脚本/管理台)经常重试,
            # 重复注册抛 Conflict 只会逼人家先查一遍再写,没意义
            return existing
        row = TenantRegistryModel(tenant_id=tid, name=name, plan=plan)
        self.session.add(row)
        self.session.flush()
        return row

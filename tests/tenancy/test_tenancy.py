"""tenancy 包全量:解析/缓存键/过滤/防护/注册表。"""

from __future__ import annotations

import pytest
from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, mapped_column

import vela.tenancy  # noqa: F401  模型注册进 Base.metadata
from vela.config.constants import TENANT_HEADER
from vela.config.errors import TenantError
from vela.db import Base, PkMixin, TenantColumnMixin
from vela.db.tenant import tenant_context
from vela.tenancy import (
    TenantRegistry,
    TenantRegistryModel,
    apply_tenant_filter,
    audit_cross_tenant_access,
    cache_key,
    ensure_same_tenant,
    require_explicit_tenant,
    resolve,
    resolve_from_host,
    scoped,
)
from vela.tenancy.models import Plan


# 临时探针模型,专门测"带 tenant_id 列走过滤"的分支
class _ProbeModel(Base, PkMixin, TenantColumnMixin):
    __tablename__ = "tenancy_probe"
    name: Mapped[str] = mapped_column(String(32))


# 无租户列的全局表,测"无列跳过"分支
class _GlobalProbeModel(Base, PkMixin):
    __tablename__ = "tenancy_probe_global"
    name: Mapped[str] = mapped_column(String(32))


class TestResolve:
    def test_default_main(self):
        assert resolve({}) == "main"

    def test_from_header_normalized(self):
        assert resolve({TENANT_HEADER: "  Acme "}) == "acme"

    def test_invalid_raises(self):
        with pytest.raises(TenantError):
            resolve({TENANT_HEADER: "bad_tenant!"})

    def test_host_subdomain(self):
        assert resolve_from_host("acme.api.vela.internal") == "acme"

    def test_host_reserved_first_label(self):
        # 平台自身域名不算租户
        assert resolve_from_host("api.acme.vela.internal") == "main"

    def test_host_no_subdomain(self):
        assert resolve_from_host("vela.internal") == "main"

    def test_host_empty(self):
        assert resolve_from_host("") == "main"


class TestCacheKey:
    def test_basic(self):
        assert cache_key("order", "123") == "t:main:order:123"

    def test_explicit_tenant(self):
        assert cache_key("order", "123", tenant="acme") == "t:acme:order:123"

    def test_with_tenant_context(self):
        with tenant_context("acme"):
            assert cache_key("sku", "s1") == "t:acme:sku:s1"

    def test_empty_parts(self):
        with pytest.raises(ValueError):
            cache_key()

    def test_scoped_already_prefixed(self):
        assert scoped("t:acme:order:1") == "t:acme:order:1"

    def test_scoped_adds_prefix(self):
        with tenant_context("acme"):
            assert scoped("order:1") == "t:acme:order:1"


class TestApplyTenantFilter:
    def test_model_with_tenant_column(self):
        with tenant_context("acme"):
            stmt = apply_tenant_filter(select(_ProbeModel), _ProbeModel)
        compiled = str(stmt.compile())
        assert "tenant_id" in compiled
        assert stmt.compile().params["tenant_id_1"] == "acme"

    def test_model_without_tenant_column_skipped(self):
        # 全局表没有 tenant_id 列,原样返回不套条件
        stmt = apply_tenant_filter(select(_GlobalProbeModel), _GlobalProbeModel)
        assert "WHERE" not in str(stmt.compile())


class TestEnsureSameTenant:
    def test_same_ok(self):
        a = TenantRegistryModel(tenant_id="acme", name="A")
        b = TenantRegistryModel(tenant_id="acme", name="B")
        ensure_same_tenant(a, b)

    def test_mismatch_raises(self):
        a = TenantRegistryModel(tenant_id="acme", name="A")
        b = TenantRegistryModel(tenant_id="other", name="B")
        with pytest.raises(TenantError):
            ensure_same_tenant(a, b)

    def test_missing_attr_treated_as_none(self):
        ensure_same_tenant(object(), object())


class TestGuard:
    def test_require_explicit_ok(self):
        assert require_explicit_tenant("acme", action="export_orders") == "acme"

    def test_require_explicit_missing(self):
        with pytest.raises(TenantError):
            require_explicit_tenant(None, action="export_orders")
        with pytest.raises(TenantError):
            require_explicit_tenant("", action="purge")

    def test_cross_tenant_flagged(self, caplog):
        assert audit_cross_tenant_access("acme", "other", "export") is True
        records = [r for r in caplog.records if r.msg == "cross_tenant_access"]
        assert records and records[0].source_tenant == "acme"

    def test_same_tenant_quiet(self, caplog):
        assert audit_cross_tenant_access("acme", "acme", "export") is False
        assert not [r for r in caplog.records if r.msg == "cross_tenant_access"]


class TestRegistry:
    def test_register_and_find(self, db_session):
        reg = TenantRegistry(db_session)
        row = reg.register("acme", " Acme 公司 ", plan="PRO")
        assert row.id is not None
        assert row.plan == "PRO"
        assert row.enabled is True
        assert reg.find_by_tenant("acme") is row

    def test_register_default_plan(self, db_session):
        reg = TenantRegistry(db_session)
        assert reg.register("beta", "B").plan == Plan.FREE.value

    def test_register_idempotent(self, db_session):
        # 重试同租户拿回同一行,不报 Conflict
        reg = TenantRegistry(db_session)
        first = reg.register("acme", "第一次")
        again = reg.register("acme", "第二次")
        assert again.id == first.id
        assert again.name == "第一次"

    def test_register_bad_tenant(self, db_session):
        reg = TenantRegistry(db_session)
        with pytest.raises(TenantError):
            reg.register("Bad_Tenant", "x")

    def test_register_bad_plan(self, db_session):
        reg = TenantRegistry(db_session)
        with pytest.raises(ValueError):
            reg.register("acme", "x", plan="ULTIMATE")

    def test_is_active(self, db_session):
        reg = TenantRegistry(db_session)
        row = reg.register("acme", "A")
        assert reg.is_active("acme") is True
        assert reg.is_active("nobody") is False
        row.enabled = False
        db_session.flush()
        assert reg.is_active("acme") is False

    def test_list_active(self, db_session):
        reg = TenantRegistry(db_session)
        a = reg.register("acme", "A")
        reg.register("beta", "B")
        a.enabled = False
        db_session.flush()
        assert [r.tenant_id for r in reg.list_active()] == ["beta"]

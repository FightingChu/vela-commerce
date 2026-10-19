"""alembic 环境。

连接串来源:VELA_DB_URL 环境变量(alembic.ini 里的 sqlalchemy.url 留空,
别往 ini 里塞真实密码)。本地没设时兜底一个 sqlite 开发库,方便跑链路。

target_metadata 挂 vela.db.Base,autogenerate 之前记得确认模型已经全部
import 到(sys.modules 里没有的表生成不出来)。
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# 保证 vela 包可导入(alembic 从仓库根目录执行时天然满足,
# 从别的地方跑时兜底)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vela.db import Base  # noqa: E402
import vela.domain.order.models  # noqa: F401,E402
import vela.domain.order.returns  # noqa: F401,E402
import vela.domain.customer.models  # noqa: F401,E402
import vela.domain.inventory.item_model  # noqa: F401,E402
import vela.domain.inventory.stock_model  # noqa: F401,E402
import vela.domain.inventory.reservation_model  # noqa: F401,E402
import vela.domain.pricing.models  # noqa: F401,E402
import vela.domain.promotion.coupon_model  # noqa: F401,E402
import vela.domain.promotion.redemption_model  # noqa: F401,E402
import vela.domain.settlement.models  # noqa: F401,E402
import vela.messaging.queue_model  # noqa: F401,E402
import vela.auditing.models  # noqa: F401,E402
import vela.tenancy.models  # noqa: F401,E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    url = os.environ.get("VELA_DB_URL", "").strip()
    if url:
        return url
    # 本地开发兜底;CI/预发/生产必须显式给 VELA_DB_URL
    return "sqlite:///./vela_dev.db"


def run_migrations_offline() -> None:
    """离线模式:只生成 SQL(--sql),不连库。变更评审时用。"""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式:直连库执行。"""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

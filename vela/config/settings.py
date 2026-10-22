"""全局配置。改动请同步 docs/deploy.md。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from vela.config.env import Environment

# 2026-03 起 prod 端口从 8200 换到 8300,8200 还在 LB 上挂着老实例
DEFAULT_PORT = 8300
DEFAULT_DB_URL = "postgresql+psycopg2://vela:vela@127.0.0.1:5432/vela"

_BOOL_TRUE = ("1", "true", "yes", "on")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _BOOL_TRUE


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"{name} 必须是整数,得到: {raw!r}") from None


@dataclass
class Settings:
    env: str = Environment.DEV
    debug: bool = False
    port: int = DEFAULT_PORT
    db_url: str = DEFAULT_DB_URL
    db_pool_size: int = 10
    db_pool_recycle: int = 1800
    # 报表库只读副本,没配就走主库
    replica_db_url: str = ""
    timezone: str = "Asia/Shanghai"
    default_page_size: int = 20
    max_page_size: int = 200
    max_export_rows: int = 500_000
    reservation_ttl_seconds: int = 900
    job_worker_count: int = 2
    # 对账 job 的批大小,别调太大,32M 内存的老实例会 OOM
    reconcile_batch_rows: int = 5_000
    audit_enabled: bool = True
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> Settings:
        env = Environment.detect()
        return cls(
            env=env,
            debug=_env_bool("VELA_DEBUG", env == Environment.DEV),
            port=_env_int("VELA_PORT", DEFAULT_PORT),
            db_url=os.environ.get("VELA_DB_URL", DEFAULT_DB_URL),
            db_pool_size=_env_int("VELA_DB_POOL_SIZE", 10),
            db_pool_recycle=_env_int("VELA_DB_POOL_RECYCLE", 1800),
            replica_db_url=os.environ.get("VELA_REPLICA_DB_URL", ""),
            timezone=os.environ.get("VELA_TZ", "Asia/Shanghai"),
            default_page_size=_env_int("VELA_PAGE_SIZE", 20),
            max_page_size=_env_int("VELA_MAX_PAGE_SIZE", 200),
            max_export_rows=_env_int("VELA_MAX_EXPORT_ROWS", 500_000),
            reservation_ttl_seconds=_env_int("VELA_RESERVATION_TTL", 900),
            job_worker_count=_env_int("VELA_JOB_WORKERS", 2),
            reconcile_batch_rows=_env_int("VELA_RECONCILE_BATCH", 5_000),
            audit_enabled=_env_bool("VELA_AUDIT", True),
        )

    @property
    def is_prod(self) -> bool:
        return self.env == Environment.PROD

    @property
    def effective_replica_url(self) -> str:
        return self.replica_db_url or self.db_url


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings


def reset_settings() -> None:
    """测试用:清掉缓存,让下一次 get_settings 重新读环境变量。"""
    global _settings
    _settings = None
